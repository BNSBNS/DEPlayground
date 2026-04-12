"""Unit tests for FeatureBuilder."""

from __future__ import annotations

import pandas as pd
import pytest

from src.ml.features.builder import FeatureBuilder
from src.ml.features.schema import FeatureFrame


def test_build_produces_feature_frame(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)

    assert isinstance(ff, FeatureFrame)
    assert len(ff) > 0
    assert ff.target == "vwap"
    assert "vwap" not in ff.feature_columns


def test_feature_hash_is_deterministic(raw_aggregates: pd.DataFrame) -> None:
    ff1 = FeatureBuilder().build(raw_aggregates)
    ff2 = FeatureBuilder().build(raw_aggregates.copy())
    assert ff1.feature_hash == ff2.feature_hash


def test_lag_features_present(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    for lag in (1, 5, 15, 30, 60):
        assert f"vwap_lag_{lag}" in ff.feature_columns


def test_calendar_features_cyclical(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    for col in ("hour_sin", "hour_cos", "dow_sin", "dow_cos"):
        assert col in ff.feature_columns
        assert ff.data[col].between(-1.0, 1.0).all()


def test_no_nan_in_feature_matrix(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    assert not ff.x.isna().any().any()
    assert not ff.y.isna().any()


def test_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty DataFrame"):
        FeatureBuilder().build(pd.DataFrame())
