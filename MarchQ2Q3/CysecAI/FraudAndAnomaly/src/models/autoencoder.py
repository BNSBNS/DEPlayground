"""PyTorch autoencoder for unsupervised anomaly detection.

Trained on normal transactions only. Fraud = high reconstruction error.
Architecture: input → 64 → 32 → 64 → input.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from src.models.base import BaseDetector, Explanation


class _Autoencoder(nn.Module):
    """Symmetric autoencoder: input → 64 → 32 → 64 → input."""

    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded: torch.Tensor = self.decoder(encoded)
        return decoded


class AutoencoderDetector(BaseDetector):
    """Unsupervised fraud detection via reconstruction error."""

    def __init__(
        self,
        epochs: int = 50,
        batch_size: int = 256,
        learning_rate: float = 1e-3,
        random_state: int = 42,
    ) -> None:
        self._epochs = epochs
        self._batch_size = batch_size
        self._lr = learning_rate
        self._random_state = random_state
        self._model: _Autoencoder | None = None
        self._threshold: float = 0.0
        self._train_mean: np.ndarray | None = None
        self._train_std: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        """Train on normal samples only. If y given, filters to y==0."""
        torch.manual_seed(self._random_state)

        X_normal = X[y == 0] if y is not None else X

        # Standardize features
        self._train_mean = np.array(X_normal.mean(axis=0))
        self._train_std = np.array(X_normal.std(axis=0))
        self._train_std[self._train_std < 1e-10] = 1.0
        X_scaled = (X_normal - self._train_mean) / self._train_std

        tensor = torch.tensor(X_scaled, dtype=torch.float32)
        loader = DataLoader(TensorDataset(tensor), batch_size=self._batch_size, shuffle=True)

        self._model = _Autoencoder(X.shape[1])
        optimizer = torch.optim.Adam(self._model.parameters(), lr=self._lr)
        criterion = nn.MSELoss()

        self._model.train()
        for _ in range(self._epochs):
            for (batch,) in loader:
                output = self._model(batch)
                loss = criterion(output, batch)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        # Set threshold as 95th percentile of normal reconstruction error
        self._model.eval()
        with torch.no_grad():
            recon = self._model(tensor)
            errors: np.ndarray = ((tensor - recon) ** 2).mean(dim=1).numpy()
        self._threshold = float(np.percentile(errors, 95))

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Binary predictions: 1 if reconstruction error > threshold."""
        scores = self.score(X)
        result: np.ndarray = (scores > self._threshold).astype(int)
        return result

    def score(self, X: np.ndarray) -> np.ndarray:
        """Mean squared reconstruction error per sample."""
        assert self._model is not None
        assert self._train_mean is not None and self._train_std is not None

        X_scaled = (X - self._train_mean) / self._train_std
        tensor = torch.tensor(X_scaled, dtype=torch.float32)

        self._model.eval()
        with torch.no_grad():
            recon = self._model(tensor)
            errors: np.ndarray = ((tensor - recon) ** 2).mean(dim=1).numpy()
        return errors

    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        """Top 3 features by per-feature reconstruction error."""
        assert self._model is not None
        assert self._train_mean is not None and self._train_std is not None

        X_scaled = (X - self._train_mean) / self._train_std
        tensor = torch.tensor(X_scaled, dtype=torch.float32)

        self._model.eval()
        with torch.no_grad():
            recon = self._model(tensor)
            per_feature_err: np.ndarray = ((tensor - recon) ** 2).numpy()

        results: list[Explanation] = []
        for i in range(X.shape[0]):
            top_idx = np.argsort(per_feature_err[i])[-3:][::-1]
            results.append([(feature_names[j], float(per_feature_err[i, j])) for j in top_idx])
        return results

    @property
    def reconstruction_threshold(self) -> float:
        """Threshold for anomaly classification."""
        return self._threshold

    def state_dict(self) -> dict[str, Any]:
        """Return model state for serialization."""
        assert self._model is not None
        return {
            "model": self._model.state_dict(),
            "threshold": self._threshold,
            "train_mean": self._train_mean,
            "train_std": self._train_std,
        }
