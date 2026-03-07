"""Abstract base class for all fraud detection models.

Every detector must implement fit(), predict(), score(), and explain().
The explain() method returns per-sample top-3 contributing features.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

Explanation = list[tuple[str, float]]


class BaseDetector(ABC):
    """ABC for fraud detection models."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        """Train the model on feature matrix X with optional labels y."""

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return binary predictions (0=normal, 1=fraud)."""

    @abstractmethod
    def score(self, X: np.ndarray) -> np.ndarray:
        """Return anomaly/fraud scores (higher = more suspicious)."""

    @abstractmethod
    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        """Return top 3 contributing features per sample."""
