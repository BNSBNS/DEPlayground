"""Training pipeline — the "command" side of CQRS.

Single entry point ``TrainingPipeline.run(model_name, symbol)``:

    1. load history   - FeatureRepository
    2. build features - FeatureBuilder
    3. walk-forward   - WalkForwardSplitter + Evaluator
    4. fit on all data
    5. persist artifact to ModelStore
    6. record metadata in model_registry

Every step emits a structlog event. No direct library imports — everything
is resolved through the registry + Protocols so any of the five model
strategies plug in without conditional logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np

from src.common.logging_config import get_logger
from src.ml.domain.models import ModelMetadata
from src.ml.pipeline.evaluation import WalkForwardSplitter, compute_all

if TYPE_CHECKING:
    import pandas as pd

    from src.ml.domain.ports import (
        FeatureRepository,
        ForecastModel,
        ModelRegistryRepository,
        ModelStore,
    )
    from src.ml.features.builder import FeatureBuilder
    from src.ml.features.schema import FeatureFrame
    from src.ml.models.registry import ModelRegistry

logger = get_logger(__name__)


class TrainingPipeline:
    """Orchestrates training end-to-end for a single model + symbol pair."""

    def __init__(
        self,
        feature_repo: FeatureRepository,
        model_store: ModelStore,
        registry_repo: ModelRegistryRepository,
        model_registry: ModelRegistry,
        feature_builder: FeatureBuilder,
        train_history_days: int = 30,
        eval_folds: int = 3,
        min_train_rows: int = 500,
        horizon: int = 15,
    ) -> None:
        self._feature_repo = feature_repo
        self._model_store = model_store
        self._registry_repo = registry_repo
        self._model_registry = model_registry
        self._feature_builder = feature_builder
        self._train_history_days = train_history_days
        self._eval_folds = eval_folds
        self._min_train_rows = min_train_rows
        self._horizon = horizon

    def run(
        self,
        model_name: str,
        symbol: str,
        hparams: dict[str, Any] | None = None,
    ) -> ModelMetadata:
        """Train a model end-to-end and return its metadata."""
        hparams = hparams or {}
        hparams.setdefault("symbol", symbol)

        logger.info("Training started", model=model_name, symbol=symbol)

        # 1. Load raw history.
        end = datetime.now(UTC)
        start = end - timedelta(days=self._train_history_days)
        raw = self._feature_repo.load_history(symbol, start, end)
        if raw.empty:
            raise ValueError(
                f"No trade_aggregates rows for symbol={symbol} "
                f"between {start.isoformat()} and {end.isoformat()}"
            )

        # 2. Build features.
        feature_frame = self._feature_builder.build(raw)
        feature_frame.data.attrs["feature_hash"] = feature_frame.feature_hash
        logger.info(
            "Features built",
            rows=len(feature_frame),
            columns=len(feature_frame.feature_columns),
            feature_hash=feature_frame.feature_hash,
        )

        # 3. Walk-forward evaluation.
        fold_metrics = self._walk_forward_eval(model_name, hparams, feature_frame)

        # 4. Fit final model on all data.
        logger.info("Fitting final model on full dataset")
        final_model = self._create_model(model_name, hparams)
        feature_frame.data.attrs["feature_hash"] = feature_frame.feature_hash
        metadata = final_model.fit(
            self._with_hash(feature_frame.x, feature_frame.feature_hash),
            feature_frame.y,
        )

        # 5. Persist artifact.
        artifact_uri = final_model.save(self._model_store)

        # 6. Register lineage.
        averaged_metrics = self._average_metrics(fold_metrics)
        final_metadata = ModelMetadata(
            model_name=metadata.model_name,
            model_version=metadata.model_version,
            trained_at=metadata.trained_at,
            metrics={**metadata.metrics, **averaged_metrics},
            params={**metadata.params, "feature_hash": feature_frame.feature_hash},
            artifact_uri=artifact_uri,
        )
        self._registry_repo.save(final_metadata)

        logger.info(
            "Training complete",
            model=model_name,
            symbol=symbol,
            metrics=final_metadata.metrics,
            artifact_uri=artifact_uri,
        )
        return final_metadata

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _walk_forward_eval(
        self,
        model_name: str,
        hparams: dict[str, Any],
        ff: FeatureFrame,
    ) -> list[dict[str, float]]:
        splitter = WalkForwardSplitter(
            n_folds=self._eval_folds,
            min_train_size=self._min_train_rows,
            horizon=self._horizon,
        )

        fold_metrics: list[dict[str, float]] = []
        for fold_idx, (train_ff, val_ff) in enumerate(splitter.split(ff)):
            model = self._create_model(model_name, hparams)
            model.fit(
                self._with_hash(train_ff.x, ff.feature_hash),
                train_ff.y,
            )
            batch = model.predict(
                self._with_hash(val_ff.x, ff.feature_hash),
                horizon=len(val_ff),
            )
            y_true = val_ff.y.to_numpy()
            y_pred = np.array([float(f.yhat) for f in batch.forecasts[: len(y_true)]])
            # Pad if model produced fewer forecasts than validation points.
            if len(y_pred) < len(y_true):
                y_true = y_true[: len(y_pred)]
            metrics = compute_all(y_true, y_pred)
            fold_metrics.append(metrics)
            logger.info(
                "Walk-forward fold",
                fold=fold_idx,
                metrics=metrics,
                train_rows=len(train_ff),
                val_rows=len(val_ff),
            )

        return fold_metrics

    def _create_model(self, model_name: str, hparams: dict[str, Any]) -> ForecastModel:
        return self._model_registry.create(model_name, **hparams)

    @staticmethod
    def _average_metrics(fold_metrics: list[dict[str, float]]) -> dict[str, float]:
        if not fold_metrics:
            return {}
        keys = fold_metrics[0].keys()
        return {f"cv_{k}": float(np.nanmean([m[k] for m in fold_metrics])) for k in keys}

    @staticmethod
    def _with_hash(x: pd.DataFrame, feature_hash: str) -> pd.DataFrame:
        # pandas DataFrame.attrs doesn't survive copies; re-attach before passing.
        x.attrs["feature_hash"] = feature_hash
        return x
