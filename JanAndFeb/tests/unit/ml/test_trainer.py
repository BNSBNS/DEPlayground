"""Unit tests for the training pipeline using in-memory fakes.

This exercises the full end-to-end path — load → features → walk-forward →
fit → save → register — without touching Postgres, so it stays a unit test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.ml.domain.models import ForecastBatch, ModelMetadata
from src.ml.features.builder import FeatureBuilder
from src.ml.models.gradient.lightgbm_model import LightGBMForecaster
from src.ml.models.registry import ModelRegistry
from src.ml.pipeline.trainer import TrainingPipeline
from src.ml.store.filesystem import FilesystemModelStore

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    import pandas as pd


class _InMemoryFeatureRepo:
    def __init__(self, data: pd.DataFrame) -> None:
        self._data = data

    def load_history(
        self,
        symbol: str,  # noqa: ARG002
        start: datetime,  # noqa: ARG002
        end: datetime,  # noqa: ARG002
    ) -> pd.DataFrame:
        return self._data.copy()


class _InMemoryRegistryRepo:
    def __init__(self) -> None:
        self.saved: list[ModelMetadata] = []

    def save(self, metadata: ModelMetadata) -> None:
        self.saved.append(metadata)

    def load_latest(self, model_name: str) -> ModelMetadata | None:
        for meta in reversed(self.saved):
            if meta.model_name == model_name:
                return meta
        return None

    def list_all(self) -> list[ModelMetadata]:
        return list(self.saved)


class _InMemoryForecastRepo:
    def __init__(self) -> None:
        self.saved: list[ForecastBatch] = []

    def save(self, batch: ForecastBatch) -> None:
        self.saved.append(batch)

    def load_latest(
        self,
        symbol: str,  # noqa: ARG002
        model_name: str,  # noqa: ARG002
        limit: int = 100,  # noqa: ARG002
    ) -> ForecastBatch:
        return self.saved[-1] if self.saved else ForecastBatch(forecasts=[])


def test_training_pipeline_end_to_end(raw_aggregates: pd.DataFrame, tmp_path: Path) -> None:
    feature_repo = _InMemoryFeatureRepo(raw_aggregates)
    registry_repo = _InMemoryRegistryRepo()
    store = FilesystemModelStore(tmp_path)

    model_registry = ModelRegistry()
    model_registry.register(
        "lightgbm",
        lambda **kw: LightGBMForecaster(n_estimators=20, **kw),
    )

    pipeline = TrainingPipeline(
        feature_repo=feature_repo,
        model_store=store,
        registry_repo=registry_repo,
        model_registry=model_registry,
        feature_builder=FeatureBuilder(),
        train_history_days=1,
        eval_folds=2,
        min_train_rows=200,
        horizon=10,
    )

    metadata = pipeline.run("lightgbm", symbol="POWER_DE")

    assert metadata.model_name == "lightgbm"
    assert metadata.artifact_uri
    assert len(registry_repo.saved) == 1
    assert "cv_mae" in metadata.metrics
