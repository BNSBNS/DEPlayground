"""Weighted ensemble combining multiple fraud detectors.

Normalizes scores from each detector to [0,1] and combines
with configurable weights. Explanation merges top features from all models.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import f1_score

from src.models.base import BaseDetector, Explanation


class EnsembleDetector(BaseDetector):
    """Weighted score combination of multiple fraud detectors."""

    def __init__(
        self,
        detectors: list[BaseDetector],
        weights: list[float] | None = None,
    ) -> None:
        if weights is not None and len(weights) != len(detectors):
            msg = "weights must match number of detectors"
            raise ValueError(msg)
        self._detectors = detectors
        self._weights = np.array(weights if weights else [1.0] * len(detectors))
        self._weights = self._weights / self._weights.sum()
        self._threshold: float = 0.5

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        """Optimize threshold on combined scores. Detectors must be pre-trained."""
        if y is not None:
            self._threshold = self._optimize_threshold(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Binary predictions using optimized threshold on combined score."""
        scores = self.score(X)
        result: np.ndarray = (scores >= self._threshold).astype(int)
        return result

    def score(self, X: np.ndarray) -> np.ndarray:
        """Weighted combination of normalized detector scores."""
        raw_scores = [d.score(X) for d in self._detectors]
        normalized = [self._normalize(s) for s in raw_scores]
        combined = np.zeros(X.shape[0])
        for w, s in zip(self._weights, normalized, strict=True):
            combined += w * s
        return combined

    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        """Merge explanations from all detectors, keeping top 3 by contribution."""
        all_explanations = [d.explain(X, feature_names) for d in self._detectors]
        n_samples = X.shape[0]
        results: list[Explanation] = []

        for i in range(n_samples):
            merged: dict[str, float] = {}
            for det_idx, det_exps in enumerate(all_explanations):
                w = float(self._weights[det_idx])
                for name, val in det_exps[i]:
                    merged[name] = merged.get(name, 0.0) + w * val
            top3 = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:3]
            results.append(top3)
        return results

    @staticmethod
    def _normalize(scores: np.ndarray) -> np.ndarray:
        """Min-max normalize to [0, 1]."""
        s_min, s_max = scores.min(), scores.max()
        if s_max - s_min < 1e-10:
            return np.zeros_like(scores)
        result: np.ndarray = (scores - s_min) / (s_max - s_min)
        return result

    def _optimize_threshold(self, X: np.ndarray, y: np.ndarray) -> float:
        """Find threshold maximizing F1 on combined scores."""
        scores = self.score(X)
        best_f1 = 0.0
        best_t = 0.5
        for t in np.arange(0.1, 0.9, 0.05):
            preds = (scores >= t).astype(int)
            f1 = float(f1_score(y, preds))
            if f1 > best_f1:
                best_f1 = f1
                best_t = float(t)
        return best_t

    @property
    def weights(self) -> np.ndarray:
        """Current detector weights."""
        return self._weights.copy()

    @property
    def threshold(self) -> float:
        """Current classification threshold."""
        return self._threshold
