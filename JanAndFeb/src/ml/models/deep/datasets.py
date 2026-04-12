"""PyTorch Dataset for sliding-window sequence forecasting.

Given a 2D feature matrix (rows=time, cols=features) and a 1D target vector,
produce ``(window, target)`` tensor pairs where ``window`` has shape
``(seq_len, n_features)`` and ``target`` has shape ``(horizon,)``.

This is the one place where the "pandas world" turns into the "tensor world"
for training. Kept tiny and dependency-free so it's easy to read and test.
"""

from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset


class SlidingWindowDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    """Windowed sequence Dataset for multi-step forecasting."""

    def __init__(
        self,
        features: np.ndarray,
        target: np.ndarray,
        seq_len: int,
        horizon: int,
    ) -> None:
        if features.ndim != 2:
            raise ValueError(f"features must be 2D (time, feat); got {features.shape}")
        if target.ndim != 1:
            raise ValueError(f"target must be 1D; got {target.shape}")
        if len(features) != len(target):
            raise ValueError(
                f"features and target must share length; got {len(features)} vs {len(target)}"
            )
        if len(features) < seq_len + horizon:
            raise ValueError(
                f"Need at least seq_len + horizon = {seq_len + horizon} rows; got {len(features)}"
            )

        self._features = features.astype(np.float32)
        self._target = target.astype(np.float32)
        self._seq_len = seq_len
        self._horizon = horizon

    def __len__(self) -> int:
        return len(self._features) - self._seq_len - self._horizon + 1

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        x = self._features[idx : idx + self._seq_len]
        y = self._target[idx + self._seq_len : idx + self._seq_len + self._horizon]
        return torch.from_numpy(x), torch.from_numpy(y)
