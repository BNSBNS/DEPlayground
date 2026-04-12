"""Unit tests for the evaluation module (metrics + walk-forward splitter)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from src.ml.features.builder import FeatureBuilder
from src.ml.pipeline.evaluation import (
    WalkForwardSplitter,
    compute_all,
    mae,
    mape,
    pinball_loss,
    rmse,
    smape,
)

if TYPE_CHECKING:
    import pandas as pd


# ------------------------------ metrics -----------------------------------
def test_mae_perfect_prediction() -> None:
    y = np.array([1.0, 2.0, 3.0])
    assert mae(y, y) == 0.0


def test_rmse_simple() -> None:
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 2.0, 4.0])
    assert rmse(y_true, y_pred) == pytest.approx(np.sqrt(1 / 3))


def test_mape_handles_nonzero() -> None:
    y_true = np.array([100.0, 200.0])
    y_pred = np.array([110.0, 180.0])
    assert mape(y_true, y_pred) == pytest.approx(10.0)


def test_mape_all_zero_returns_nan() -> None:
    y_true = np.array([0.0, 0.0])
    y_pred = np.array([1.0, 2.0])
    assert np.isnan(mape(y_true, y_pred))


def test_smape_bounded() -> None:
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([10.0, 20.0, 30.0])
    assert 0 <= smape(y_true, y_pred) <= 200


def test_pinball_loss_valid_alpha() -> None:
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 2.0, 3.0])
    assert pinball_loss(y_true, y_pred, alpha=0.5) == 0.0


def test_pinball_loss_invalid_alpha() -> None:
    y = np.array([1.0])
    with pytest.raises(ValueError):
        pinball_loss(y, y, alpha=1.5)


def test_compute_all_returns_all_keys() -> None:
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.1, 2.1, 2.9, 4.2])
    metrics = compute_all(y_true, y_pred)
    assert set(metrics.keys()) == {"mae", "rmse", "mape", "smape"}


# ------------------------- walk-forward splitter --------------------------
def test_walk_forward_yields_n_folds(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    splitter = WalkForwardSplitter(n_folds=3, min_train_size=100, horizon=20)
    folds = list(splitter.split(ff))
    assert len(folds) == 3


def test_walk_forward_train_grows_monotonically(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    splitter = WalkForwardSplitter(n_folds=3, min_train_size=100, horizon=20)
    prev_train_len = 0
    for train, val in splitter.split(ff):
        assert len(train) > prev_train_len
        assert len(val) == 20
        # val must come AFTER train
        assert train.data.index[-1] < val.data.index[0]
        prev_train_len = len(train)


def test_walk_forward_requires_enough_data(raw_aggregates: pd.DataFrame) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    splitter = WalkForwardSplitter(n_folds=10, min_train_size=100000, horizon=100)
    with pytest.raises(ValueError, match="requires at least"):
        list(splitter.split(ff))
