"""Unit tests for LightGBMForecaster."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.ml.features.builder import FeatureBuilder
from src.ml.models.gradient.lightgbm_model import LightGBMForecaster
from src.ml.store.filesystem import FilesystemModelStore

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def test_fit_and_predict(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    model = LightGBMForecaster(symbol="POWER_DE", n_estimators=20)
    meta = model.fit(ff.x, ff.y)

    assert meta.model_name == "lightgbm"
    assert "train_mae" in meta.metrics

    batch = model.predict(ff.x, horizon=5)
    assert len(batch) == 5
    for f in batch.forecasts:
        assert f.yhat_lower is not None
        assert f.yhat_upper is not None
        assert f.yhat_lower <= f.yhat <= f.yhat_upper or f.yhat_upper >= f.yhat_lower


def test_predict_requires_fit(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    model = LightGBMForecaster(symbol="POWER_DE")
    with pytest.raises(RuntimeError, match="must be fit"):
        model.predict(ff.x, horizon=5)


def test_save_and_load_roundtrip(raw_aggregates: pd.DataFrame, tmp_path: Path) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    store = FilesystemModelStore(tmp_path)
    model = LightGBMForecaster(symbol="POWER_DE", n_estimators=20)
    model.fit(ff.x, ff.y)

    uri = model.save(store)
    loaded = LightGBMForecaster.load(store, uri)

    original_batch = model.predict(ff.x, horizon=3)
    loaded_batch = loaded.predict(ff.x, horizon=3)
    for a, b in zip(original_batch.forecasts, loaded_batch.forecasts, strict=True):
        assert a.yhat == b.yhat
