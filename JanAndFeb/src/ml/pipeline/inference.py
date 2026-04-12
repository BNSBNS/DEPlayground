"""Inference service — the "query" side of CQRS.

Loads the latest model from the registry, caches it in memory, and serves
predictions on demand. Persists every prediction back to the ``forecasts``
table so the API can return cached results via simple SQL queries instead
of re-running the model on every request.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.common.logging_config import get_logger

if TYPE_CHECKING:
    from src.ml.domain.models import ForecastBatch
    from src.ml.domain.ports import (
        FeatureRepository,
        ForecastModel,
        ForecastRepository,
        ModelRegistryRepository,
        ModelStore,
    )
    from src.ml.features.builder import FeatureBuilder

logger = get_logger(__name__)

# A small in-process cache; in production this would be an LRU with eviction,
# but for learning purposes a plain dict keyed by (name, version) is clearer.
_CacheKey = tuple[str, str]


class InferenceService:
    """Loads models lazily and serves forecasts."""

    def __init__(
        self,
        feature_repo: FeatureRepository,
        forecast_repo: ForecastRepository,
        registry_repo: ModelRegistryRepository,
        model_store: ModelStore,
        feature_builder: FeatureBuilder,
        model_loaders: dict[str, Any],
        infer_history_minutes: int = 240,
    ) -> None:
        self._feature_repo = feature_repo
        self._forecast_repo = forecast_repo
        self._registry_repo = registry_repo
        self._model_store = model_store
        self._feature_builder = feature_builder
        self._model_loaders = model_loaders
        self._infer_history_minutes = infer_history_minutes
        self._cache: dict[_CacheKey, ForecastModel] = {}

    def predict(
        self,
        symbol: str,
        model_name: str,
        horizon: int,
    ) -> ForecastBatch:
        """Produce and persist a forecast batch for ``symbol``."""
        model = self._get_or_load(model_name)

        # Build features from the last N minutes so the lag columns are fresh.
        end = datetime.now(UTC)
        start = end - timedelta(minutes=self._infer_history_minutes)
        raw = self._feature_repo.load_history(symbol, start, end)
        if raw.empty:
            raise ValueError(f"No recent history for symbol={symbol}")

        ff = self._feature_builder.build(raw)
        ff.x.attrs["feature_hash"] = ff.feature_hash

        batch = model.predict(ff.x, horizon=horizon)
        self._forecast_repo.save(batch)
        logger.info(
            "Inference completed",
            symbol=symbol,
            model=model_name,
            horizon=horizon,
            forecasts=len(batch),
        )
        return batch

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _get_or_load(self, model_name: str) -> ForecastModel:
        metadata = self._registry_repo.load_latest(model_name)
        if metadata is None:
            raise LookupError(f"No trained model found in registry: {model_name}")

        key = (model_name, metadata.model_version)
        if key in self._cache:
            return self._cache[key]

        loader = self._model_loaders.get(model_name)
        if loader is None:
            raise KeyError(f"No loader registered for model '{model_name}'")

        model: ForecastModel = loader.load(self._model_store, metadata.artifact_uri)
        self._cache[key] = model
        logger.info("Loaded model into cache", name=model_name, version=metadata.model_version)
        return model

    def invalidate_cache(self) -> None:
        """Clear the cache; call after retraining to force a reload."""
        self._cache.clear()
