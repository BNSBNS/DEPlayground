"""Forecast evaluation — pure functions and walk-forward splitting.

Walk-forward (not random k-fold) is mandatory for time series: random splits
leak future information into the training set and produce wildly optimistic
metrics. ``WalkForwardSplitter`` yields ``(train, val)`` pairs where each
validation window immediately follows its training window in time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from src.ml.features.schema import FeatureFrame

if TYPE_CHECKING:
    from collections.abc import Iterator


# ==========================================================================
# Metrics
# ==========================================================================
def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root mean squared error."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute percentage error. Returns nan if any y_true is 0."""
    mask = y_true != 0
    if not np.any(mask):
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Symmetric MAPE — bounded in [0, 200], handles zeros gracefully."""
    denom = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    mask = denom != 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / denom[mask]) * 100.0)


def pinball_loss(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    alpha: float,
) -> float:
    """Pinball (quantile) loss for evaluating quantile forecasts."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    diff = y_true - y_pred
    return float(np.mean(np.maximum(alpha * diff, (alpha - 1.0) * diff)))


def compute_all(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute the full metric suite in one call."""
    return {
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "mape": mape(y_true, y_pred),
        "smape": smape(y_true, y_pred),
    }


# ==========================================================================
# Walk-forward splitter
# ==========================================================================
@dataclass(frozen=True)
class WalkForwardSplitter:
    """Yields ``(train, val)`` ``FeatureFrame`` pairs in chronological order.

    Parameters
    ----------
    n_folds:
        Number of folds to yield.
    min_train_size:
        Minimum number of rows in the first training window.
    horizon:
        Number of rows in each validation window.
    """

    n_folds: int
    min_train_size: int
    horizon: int

    def __post_init__(self) -> None:
        if self.n_folds < 1:
            raise ValueError("n_folds must be >= 1")
        if self.min_train_size < 1:
            raise ValueError("min_train_size must be >= 1")
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")

    def split(self, ff: FeatureFrame) -> Iterator[tuple[FeatureFrame, FeatureFrame]]:
        n = len(ff)
        required = self.min_train_size + self.horizon * self.n_folds
        if n < required:
            raise ValueError(
                f"FeatureFrame has {n} rows but walk-forward with n_folds={self.n_folds}, "
                f"min_train_size={self.min_train_size}, horizon={self.horizon} "
                f"requires at least {required} rows."
            )

        # Evenly spaced fold boundaries after the warm-up window.
        step = (n - self.min_train_size) // self.n_folds
        for k in range(self.n_folds):
            train_end = self.min_train_size + k * step
            val_end = train_end + self.horizon
            yield (
                _slice(ff, 0, train_end),
                _slice(ff, train_end, val_end),
            )


def _slice(ff: FeatureFrame, start: int, end: int) -> FeatureFrame:
    """Return a FeatureFrame sliced by row index (preserves feature hash)."""
    return FeatureFrame(
        data=ff.data.iloc[start:end].copy(),
        feature_columns=ff.feature_columns,
        target=ff.target,
    )
