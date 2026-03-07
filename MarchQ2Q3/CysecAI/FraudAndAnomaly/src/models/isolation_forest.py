"""Isolation Forest anomaly detector.

Unsupervised model that isolates anomalies by random partitioning.
Uses z-score deviation from training distribution for explanations.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from src.models.base import BaseDetector, Explanation


class IsolationForestDetector(BaseDetector):
    """Unsupervised anomaly detection via Isolation Forest."""

    def __init__(
        self,
        contamination: float = 0.03,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self._model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
        )
        self._train_mean: np.ndarray | None = None
        self._train_std: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:  # noqa: ARG002
        """Fit on feature matrix (labels ignored — unsupervised)."""
        self._train_mean = np.array(X.mean(axis=0))
        self._train_std = np.array(X.std(axis=0))
        self._train_std[self._train_std < 1e-10] = 1.0
        self._model.fit(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Binary predictions: 1=fraud (anomaly), 0=normal."""
        preds: np.ndarray = self._model.predict(X)
        result: np.ndarray = (preds == -1).astype(int)
        return result

    def score(self, X: np.ndarray) -> np.ndarray:
        """Anomaly score (higher = more anomalous). Negated decision_function."""
        scores: np.ndarray = -self._model.decision_function(X)
        return scores

    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        """Top 3 features by absolute z-score deviation from training mean."""
        assert self._train_mean is not None and self._train_std is not None
        z_scores = (X - self._train_mean) / self._train_std
        results: list[Explanation] = []
        for i in range(X.shape[0]):
            top_idx = np.argsort(np.abs(z_scores[i]))[-3:][::-1]
            results.append([(feature_names[j], float(z_scores[i, j])) for j in top_idx])
        return results
