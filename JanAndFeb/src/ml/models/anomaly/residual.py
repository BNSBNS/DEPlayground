"""Residual-based anomaly detector — composition over inheritance.

The idea: a forecaster that already does a decent job of predicting tomorrow
is, *by construction*, an anomaly detector for today. Anything it gets badly
wrong is unusual. We formalize this as:

    residual = actual - baseline_prediction
    is_anomaly = |residual - mean| > k * sigma

where ``mean`` and ``sigma`` are learned from the training residuals.

The detector is composition-based: it holds a reference to an inner baseline
(either a rolling-mean series or any ``ForecastModel``-like callable) and
never inherits from it. Swap the baseline without touching the detection logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import numpy as np
import pandas as pd

from src.common.logging_config import get_logger
from src.ml.domain.models import AnomalyScore

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger(__name__)


class Baseline(Protocol):
    """Anything that can turn a feature frame into a one-column prediction.

    This is the seam that lets a SARIMAXForecaster, a LightGBMForecaster, or
    a naive rolling mean all play the same role here.
    """

    def __call__(self, features: pd.DataFrame) -> pd.Series: ...


class RollingMeanBaseline:
    """Baseline that predicts the next value as the rolling mean of recent history.

    Cheap, deterministic, and good enough to make the residual test meaningful.
    Used as the default when no forecaster is supplied.
    """

    def __init__(self, window: int = 30, target_col: str = "vwap") -> None:
        self._window = window
        self._target_col = target_col

    def __call__(self, features: pd.DataFrame) -> pd.Series:
        # ``shift(1)`` so the prediction for row i only sees rows 0..i-1 —
        # no leakage of the actual value into its own forecast.
        return (
            features[self._target_col].rolling(window=self._window, min_periods=1).mean().shift(1)
        )


class ResidualAnomalyDetector:
    """Flags rows whose residual exceeds ``k`` standard deviations.

    Parameters
    ----------
    symbol:
        Symbol the detector is bound to (stamped onto every ``AnomalyScore``).
    baseline:
        Any callable mapping a feature frame to a per-row prediction series.
        Defaults to a rolling mean of ``vwap``.
    k:
        Threshold multiplier. Classic "3-sigma rule" by default.
    target_col:
        Column in ``features`` holding the ground-truth actual.
    """

    name: str = "residual"

    def __init__(
        self,
        symbol: str = "UNKNOWN",
        baseline: Baseline | None = None,
        k: float = 3.0,
        target_col: str = "vwap",
    ) -> None:
        self.symbol = symbol
        self._baseline: Baseline = baseline or RollingMeanBaseline(target_col=target_col)
        self._k = k
        self._target_col = target_col
        self._mean: float = 0.0
        self._std: float = 1.0
        self._fitted = False

    # ------------------------------------------------------------------
    # AnomalyDetector.fit
    # ------------------------------------------------------------------
    def fit(self, features: pd.DataFrame) -> None:
        residuals = self._residuals(features).dropna()
        if residuals.empty:
            raise ValueError("ResidualAnomalyDetector: no usable residuals after warmup.")

        self._mean = float(residuals.mean())
        self._std = float(residuals.std(ddof=0)) or 1e-8
        self._fitted = True

        logger.info(
            "residual_detector_fitted",
            symbol=self.symbol,
            mean=self._mean,
            std=self._std,
            threshold=self._k,
        )

    # ------------------------------------------------------------------
    # AnomalyDetector.score
    # ------------------------------------------------------------------
    def score(self, features: pd.DataFrame) -> list[AnomalyScore]:
        if not self._fitted:
            raise RuntimeError("ResidualAnomalyDetector must be fit before score().")

        residuals = self._residuals(features)
        # Z-score in units of training residual sigma. ``nan_to_num`` keeps
        # the output array aligned with the input index (warmup rows → 0).
        z = np.nan_to_num(
            np.abs(residuals.to_numpy() - self._mean) / self._std,
            nan=0.0,
        )

        return [
            AnomalyScore(
                symbol=self.symbol,
                window_start=self._row_timestamp(features, i),
                score=float(z[i]),
                is_anomaly=bool(z[i] > self._k),
                detector_name=self.name,
            )
            for i in range(len(features))
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _residuals(self, features: pd.DataFrame) -> pd.Series:
        if self._target_col not in features.columns:
            raise KeyError(f"ResidualAnomalyDetector: target column '{self._target_col}' missing")
        actual = features[self._target_col].astype(float)
        predicted = self._baseline(features).astype(float)
        return actual - predicted

    @staticmethod
    def _row_timestamp(features: pd.DataFrame, i: int) -> datetime:
        if isinstance(features.index, pd.DatetimeIndex):
            return features.index[i].to_pydatetime()
        return pd.Timestamp.utcnow().to_pydatetime()
