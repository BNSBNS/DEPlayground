"""Tests for fraud detection models (Phase 3).

Uses a 5000-transaction dataset with stratified 80/20 split.
Module-scoped fixtures ensure models train only once per test run.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

from src.config import GeneratorSettings
from src.data.generator import TransactionGenerator
from src.features.pipeline import FeaturePipeline
from src.models.base import BaseDetector
from src.models.isolation_forest import IsolationForestDetector
from src.models.xgboost_model import XGBoostDetector

ModelData = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]


@pytest.fixture(scope="module")
def model_data() -> ModelData:
    """Feature matrix with stratified train/test split (10K transactions)."""
    settings = GeneratorSettings(num_transactions=10000, seed=42, num_users=1000)
    gen = TransactionGenerator(settings)
    txs = gen.generate()
    pipeline = FeaturePipeline()
    df = pipeline.run(txs)
    X = df[pipeline.feature_columns].values.astype(np.float64)
    y = df["is_fraud"].astype(int).values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    return X_train, X_test, y_train, y_test, list(pipeline.feature_columns)


@pytest.fixture(scope="module")
def trained_iforest(model_data: ModelData) -> IsolationForestDetector:
    """Pre-trained Isolation Forest detector."""
    X_train = model_data[0]
    model = IsolationForestDetector()
    model.fit(X_train)
    return model


@pytest.fixture(scope="module")
def trained_xgboost(model_data: ModelData) -> XGBoostDetector:
    """Pre-trained XGBoost detector."""
    X_train, _, y_train = model_data[0], model_data[1], model_data[2]
    model = XGBoostDetector()
    model.fit(X_train, y_train)
    return model


class TestBaseDetector:
    """Verify ABC cannot be instantiated directly."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseDetector()  # type: ignore[abstract]


class TestIsolationForest:
    """Isolation Forest model tests."""

    def test_predict_binary(
        self, model_data: ModelData, trained_iforest: IsolationForestDetector
    ) -> None:
        X_test = model_data[1]
        preds = trained_iforest.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_score_shape(
        self, model_data: ModelData, trained_iforest: IsolationForestDetector
    ) -> None:
        X_test = model_data[1]
        scores = trained_iforest.score(X_test)
        assert scores.shape == (len(X_test),)

    def test_fraud_scores_higher_than_normal(
        self, model_data: ModelData, trained_iforest: IsolationForestDetector
    ) -> None:
        """Anomaly scores for fraud transactions should be higher on average."""
        X_test, y_test = model_data[1], model_data[3]
        scores = trained_iforest.score(X_test)
        assert float(scores[y_test == 1].mean()) > float(scores[y_test == 0].mean())

    def test_explain_returns_top3(
        self, model_data: ModelData, trained_iforest: IsolationForestDetector
    ) -> None:
        X_test, feature_names = model_data[1], model_data[4]
        explanations = trained_iforest.explain(X_test[:5], feature_names)
        assert len(explanations) == 5
        for exp in explanations:
            assert len(exp) == 3
            for name, val in exp:
                assert name in feature_names
                assert isinstance(val, float)


class TestXGBoost:
    """XGBoost model tests."""

    def test_predict_binary(self, model_data: ModelData, trained_xgboost: XGBoostDetector) -> None:
        X_test = model_data[1]
        preds = trained_xgboost.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_f1_above_070(self, model_data: ModelData, trained_xgboost: XGBoostDetector) -> None:
        """XGBoost must achieve F1 > 0.70 on fraud class."""
        X_test, y_test = model_data[1], model_data[3]
        preds = trained_xgboost.predict(X_test)
        f1 = float(f1_score(y_test, preds))
        assert f1 > 0.70, f"F1={f1:.3f} below 0.70"

    def test_score_probabilities(
        self, model_data: ModelData, trained_xgboost: XGBoostDetector
    ) -> None:
        X_test = model_data[1]
        scores = trained_xgboost.score(X_test)
        assert scores.shape == (len(X_test),)
        assert float(scores.min()) >= 0.0
        assert float(scores.max()) <= 1.0

    def test_explain_returns_top3(
        self, model_data: ModelData, trained_xgboost: XGBoostDetector
    ) -> None:
        X_test, feature_names = model_data[1], model_data[4]
        explanations = trained_xgboost.explain(X_test[:5], feature_names)
        assert len(explanations) == 5
        for exp in explanations:
            assert len(exp) == 3
            for name, val in exp:
                assert name in feature_names
                assert isinstance(val, float)

    def test_requires_labels(self) -> None:
        model = XGBoostDetector()
        X = np.random.default_rng(42).random((10, 5))
        with pytest.raises(ValueError, match="requires labels"):
            model.fit(X)

    def test_best_params_populated(self, trained_xgboost: XGBoostDetector) -> None:
        params = trained_xgboost.best_params
        assert "max_depth" in params
        assert "learning_rate" in params
        assert "n_estimators" in params
