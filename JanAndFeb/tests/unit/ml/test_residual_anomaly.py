"""Unit tests for the residual-based anomaly detector."""

from __future__ import annotations

import pandas as pd
import pytest

from src.ml.features.builder import FeatureBuilder
from src.ml.models.anomaly.residual import (
    ResidualAnomalyDetector,
    RollingMeanBaseline,
)


def test_residual_detector_flags_large_jump(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)

    detector = ResidualAnomalyDetector(
        symbol="POWER_DE",
        baseline=RollingMeanBaseline(window=15),
        k=3.0,
    )
    detector.fit(ff.data)

    # Inject a huge jump in the last row and rescore.
    perturbed = ff.data.copy()
    last_idx = perturbed.index[-1]
    perturbed.loc[last_idx, "vwap"] = perturbed["vwap"].mean() + 50.0

    scores = detector.score(perturbed)
    assert len(scores) == len(perturbed)
    assert scores[-1].is_anomaly
    assert scores[-1].score > 3.0
    assert scores[-1].detector_name == "residual"


def test_residual_detector_quiet_on_clean_data(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    detector = ResidualAnomalyDetector(symbol="POWER_DE", k=5.0)
    detector.fit(ff.data)

    scores = detector.score(ff.data)
    # A 5-sigma threshold on clean synthetic data should flag almost nothing.
    anomalies = sum(1 for s in scores if s.is_anomaly)
    assert anomalies <= max(1, int(0.02 * len(scores)))


def test_residual_detector_requires_fit(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    detector = ResidualAnomalyDetector(symbol="POWER_DE")
    with pytest.raises(RuntimeError, match="must be fit"):
        detector.score(ff.data)


def test_residual_detector_rejects_missing_target() -> None:
    detector = ResidualAnomalyDetector(symbol="POWER_DE", target_col="does_not_exist")
    with pytest.raises(KeyError, match="target column"):
        detector.fit(pd.DataFrame({"other": [1.0, 2.0]}))
