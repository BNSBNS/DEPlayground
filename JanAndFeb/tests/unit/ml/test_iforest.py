"""Unit tests for the IsolationForest anomaly detector."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.ml.features.builder import FeatureBuilder
from src.ml.models.anomaly.iforest import IsolationForestDetector

if TYPE_CHECKING:
    import pandas as pd


def test_iforest_flags_injected_spike(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    features = ff.data.copy()

    # Inject a massive spike across ALL scored features so IsolationForest
    # sees a clear outlier (single-feature spikes can get buried in noise).
    spike_idx = features.index[-1]
    features.loc[spike_idx, "vwap"] = features["vwap"].mean() * 50
    features.loc[spike_idx, "total_volume"] = features["total_volume"].mean() * 50
    features.loc[spike_idx, "price_range"] = features["price_range"].mean() * 50
    features.loc[spike_idx, "lmp_congestion"] = features["lmp_congestion"].mean() * 50

    detector = IsolationForestDetector(symbol="POWER_DE", contamination=0.02, random_state=0)
    detector.fit(features.iloc[:-1])  # train on clean data
    scores = detector.score(features)

    assert len(scores) == len(features)
    # The spike row should have the highest anomaly score of the batch.
    spike_score = scores[-1].score
    other_scores = [s.score for s in scores[:-1]]
    assert spike_score > max(other_scores)
    assert scores[-1].is_anomaly
    assert scores[-1].detector_name == "isolation_forest"
    assert scores[-1].symbol == "POWER_DE"


def test_iforest_requires_fit_before_score(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    detector = IsolationForestDetector(symbol="POWER_DE")
    with pytest.raises(RuntimeError, match="must be fit"):
        detector.score(ff.data)


def test_iforest_rejects_missing_columns(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    detector = IsolationForestDetector(
        symbol="POWER_DE", feature_columns=["vwap", "does_not_exist"]
    )
    with pytest.raises(KeyError, match="missing feature columns"):
        detector.fit(ff.data)
