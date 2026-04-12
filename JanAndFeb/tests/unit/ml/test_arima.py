"""Unit tests for SARIMAXForecaster."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.ml.features.builder import FeatureBuilder
from src.ml.models.classical.arima import SARIMAXForecaster
from src.ml.store.filesystem import FilesystemModelStore

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def test_fit_and_predict(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    model = SARIMAXForecaster(
        order=(1, 0, 0),
        seasonal_order=(0, 0, 0, 0),
        symbol="POWER_DE",
    )
    meta = model.fit(ff.x, ff.y)
    assert meta.model_name == "sarimax"
    assert "aic" in meta.metrics

    batch = model.predict(ff.x, horizon=5)
    assert len(batch) == 5
    for f in batch.forecasts:
        assert f.yhat_lower is not None
        assert f.yhat_upper is not None


def test_predict_requires_fit(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    model = SARIMAXForecaster(order=(1, 0, 0), seasonal_order=(0, 0, 0, 0))
    with pytest.raises(RuntimeError):
        model.predict(ff.x, horizon=5)


def test_save_and_load_roundtrip(raw_aggregates: pd.DataFrame, tmp_path: Path) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    store = FilesystemModelStore(tmp_path)
    model = SARIMAXForecaster(
        order=(1, 0, 0),
        seasonal_order=(0, 0, 0, 0),
        symbol="POWER_DE",
    )
    model.fit(ff.x, ff.y)
    uri = model.save(store)
    loaded = SARIMAXForecaster.load(store, uri)
    # Loaded model should be able to predict
    batch = loaded.predict(ff.x, horizon=3)
    assert len(batch) == 3
