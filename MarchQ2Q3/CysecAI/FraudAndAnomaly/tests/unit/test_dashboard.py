"""Tests for dashboard data functions (Phase 7).

Tests the data loading and model training functions, not the Streamlit UI.
"""

from __future__ import annotations

import numpy as np

from src.dashboard.app import _load_data, _train_models


class TestDashboardData:
    """Data loading tests."""

    def test_load_data_returns_tuple(self) -> None:
        data = _load_data(1000, 42)
        assert len(data) == 6

    def test_load_data_shapes(self) -> None:
        df, X_train, X_test, y_train, y_test, features = _load_data(1000, 42)
        assert len(df) == 1000
        assert X_train.shape[0] + X_test.shape[0] == 1000
        assert X_train.shape[1] == len(features)
        assert y_train.shape[0] == X_train.shape[0]
        assert y_test.shape[0] == X_test.shape[0]

    def test_features_list(self) -> None:
        _, _, _, _, _, features = _load_data(1000, 42)
        assert len(features) == 20
        assert "amount_log" in features

    def test_stratified_split(self) -> None:
        _, _, _, y_train, y_test, _ = _load_data(2000, 42)
        train_fraud_rate = y_train.mean()
        test_fraud_rate = y_test.mean()
        assert abs(train_fraud_rate - test_fraud_rate) < 0.02


class TestDashboardModels:
    """Model training tests."""

    def test_train_returns_models(self) -> None:
        _, X_train, _, y_train, _, _ = _load_data(1000, 42)
        models = _train_models(X_train, y_train, 42)
        assert "iforest" in models
        assert "xgboost" in models
        assert "ensemble" in models

    def test_ensemble_scores(self) -> None:
        _, X_train, X_test, y_train, _, _ = _load_data(1000, 42)
        models = _train_models(X_train, y_train, 42)
        scores = models["ensemble"].score(X_test)
        assert scores.shape == (X_test.shape[0],)
        assert np.all(np.isfinite(scores))

    def test_ensemble_predicts(self) -> None:
        _, X_train, X_test, y_train, _, _ = _load_data(1000, 42)
        models = _train_models(X_train, y_train, 42)
        preds = models["ensemble"].predict(X_test)
        assert set(np.unique(preds)).issubset({0, 1})
