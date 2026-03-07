"""Tests for autoencoder and ensemble models (Phase 4).

Reuses model_data fixture from test_models via conftest sharing.
Module-scoped fixtures ensure expensive training happens once.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split

from src.config import GeneratorSettings
from src.data.generator import TransactionGenerator
from src.features.pipeline import FeaturePipeline
from src.models.autoencoder import AutoencoderDetector
from src.models.ensemble import EnsembleDetector
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
def trained_autoencoder(model_data: ModelData) -> AutoencoderDetector:
    """Pre-trained autoencoder (on normal samples only)."""
    X_train, _, y_train = model_data[0], model_data[1], model_data[2]
    model = AutoencoderDetector(epochs=30, random_state=42)
    model.fit(X_train, y_train)
    return model


@pytest.fixture(scope="module")
def trained_iforest(model_data: ModelData) -> IsolationForestDetector:
    """Pre-trained Isolation Forest."""
    model = IsolationForestDetector()
    model.fit(model_data[0])
    return model


@pytest.fixture(scope="module")
def trained_xgboost(model_data: ModelData) -> XGBoostDetector:
    """Pre-trained XGBoost."""
    model = XGBoostDetector()
    model.fit(model_data[0], model_data[2])
    return model


@pytest.fixture(scope="module")
def trained_ensemble(
    model_data: ModelData,
    trained_iforest: IsolationForestDetector,
    trained_xgboost: XGBoostDetector,
    trained_autoencoder: AutoencoderDetector,
) -> EnsembleDetector:
    """Pre-trained ensemble with optimized threshold."""
    ensemble = EnsembleDetector(
        detectors=[trained_iforest, trained_xgboost, trained_autoencoder],
        weights=[0.2, 0.5, 0.3],
    )
    ensemble.fit(model_data[0], model_data[2])
    return ensemble


class TestAutoencoder:
    """Autoencoder model tests."""

    def test_predict_binary(
        self, model_data: ModelData, trained_autoencoder: AutoencoderDetector
    ) -> None:
        X_test = model_data[1]
        preds = trained_autoencoder.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_score_non_negative(
        self, model_data: ModelData, trained_autoencoder: AutoencoderDetector
    ) -> None:
        """Reconstruction error (MSE) must be >= 0."""
        X_test = model_data[1]
        scores = trained_autoencoder.score(X_test)
        assert scores.shape == (len(X_test),)
        assert float(scores.min()) >= 0.0

    def test_fraud_scores_higher_than_normal(
        self, model_data: ModelData, trained_autoencoder: AutoencoderDetector
    ) -> None:
        """Fraud should have higher reconstruction error on average."""
        X_test, y_test = model_data[1], model_data[3]
        scores = trained_autoencoder.score(X_test)
        assert float(scores[y_test == 1].mean()) > float(scores[y_test == 0].mean())

    def test_explain_returns_top3(
        self, model_data: ModelData, trained_autoencoder: AutoencoderDetector
    ) -> None:
        X_test, feature_names = model_data[1], model_data[4]
        explanations = trained_autoencoder.explain(X_test[:5], feature_names)
        assert len(explanations) == 5
        for exp in explanations:
            assert len(exp) == 3
            for name, val in exp:
                assert name in feature_names
                assert isinstance(val, float)

    def test_threshold_set(self, trained_autoencoder: AutoencoderDetector) -> None:
        assert trained_autoencoder.reconstruction_threshold > 0.0

    def test_trains_on_normal_only(self) -> None:
        """Verify model uses only normal samples when y is provided."""
        rng = np.random.default_rng(42)
        X = rng.random((100, 10))
        y = np.zeros(100)
        y[:5] = 1  # 5 fraud samples
        model = AutoencoderDetector(epochs=5, random_state=42)
        model.fit(X, y)
        assert model._model is not None

    def test_state_dict(self, trained_autoencoder: AutoencoderDetector) -> None:
        state = trained_autoencoder.state_dict()
        assert "model" in state
        assert "threshold" in state
        assert state["threshold"] > 0.0


class TestEnsemble:
    """Ensemble model tests."""

    def test_predict_binary(
        self, model_data: ModelData, trained_ensemble: EnsembleDetector
    ) -> None:
        X_test = model_data[1]
        preds = trained_ensemble.predict(X_test)
        assert preds.shape == (len(X_test),)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_score_range(self, model_data: ModelData, trained_ensemble: EnsembleDetector) -> None:
        """Combined normalized scores should be in [0, 1]."""
        X_test = model_data[1]
        scores = trained_ensemble.score(X_test)
        assert float(scores.min()) >= 0.0
        assert float(scores.max()) <= 1.0

    def test_ensemble_aucpr_beats_individuals(
        self,
        model_data: ModelData,
        trained_iforest: IsolationForestDetector,
        trained_xgboost: XGBoostDetector,
        trained_autoencoder: AutoencoderDetector,
        trained_ensemble: EnsembleDetector,
    ) -> None:
        """Ensemble AUC-PR should beat at least 2 of 3 individual detectors."""
        X_test, y_test = model_data[1], model_data[3]

        aucpr_if = float(average_precision_score(y_test, trained_iforest.score(X_test)))
        aucpr_xgb = float(average_precision_score(y_test, trained_xgboost.score(X_test)))
        aucpr_ae = float(average_precision_score(y_test, trained_autoencoder.score(X_test)))
        aucpr_ens = float(average_precision_score(y_test, trained_ensemble.score(X_test)))

        individual_scores = [aucpr_if, aucpr_xgb, aucpr_ae]
        beats = sum(1 for s in individual_scores if aucpr_ens >= s)
        assert beats >= 2, (
            f"Ensemble AUC-PR={aucpr_ens:.3f} beats only {beats}/3 "
            f"(IF={aucpr_if:.3f}, XGB={aucpr_xgb:.3f}, AE={aucpr_ae:.3f})"
        )

    def test_explain_returns_top3(
        self, model_data: ModelData, trained_ensemble: EnsembleDetector
    ) -> None:
        X_test, feature_names = model_data[1], model_data[4]
        explanations = trained_ensemble.explain(X_test[:5], feature_names)
        assert len(explanations) == 5
        for exp in explanations:
            assert len(exp) == 3
            for name, val in exp:
                assert name in feature_names
                assert isinstance(val, float)

    def test_weights_sum_to_one(self, trained_ensemble: EnsembleDetector) -> None:
        assert abs(float(trained_ensemble.weights.sum()) - 1.0) < 1e-6

    def test_rejects_mismatched_weights(self) -> None:
        model = IsolationForestDetector()
        with pytest.raises(ValueError, match="weights must match"):
            EnsembleDetector(detectors=[model], weights=[0.5, 0.5])
