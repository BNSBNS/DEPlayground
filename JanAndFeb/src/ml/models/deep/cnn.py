"""1D dilated CNN forecaster — convolution over time (mini TCN).

Stacked 1D convolutions with increasing dilation rates read ever-larger
temporal neighborhoods without the sequential cost of recurrence. Every
output position is computed in parallel, so training is much faster than
GRU on modern hardware — and often reaches comparable accuracy.
"""

from __future__ import annotations

import torch
from torch import nn

from src.ml.models.deep.base import BaseNeuralForecaster


class CNNForecaster(BaseNeuralForecaster):
    """3-layer 1D CNN with dilations (1, 2, 4) and an adaptive pool head."""

    name = "cnn"

    def build_network(self) -> nn.Module:
        channels = int(self.hparams["hidden_size"])
        input_channels = int(self.hparams["input_size"])
        dropout = float(self.hparams["dropout"])
        horizon = int(self.hparams["horizon"])

        return nn.Sequential(
            nn.Conv1d(input_channels, channels, kernel_size=3, padding=1, dilation=1),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Conv1d(channels, channels, kernel_size=3, padding=2, dilation=2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Conv1d(channels, channels, kernel_size=3, padding=4, dilation=4),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(channels, horizon),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        # x: (batch, seq_len, features) -> Conv1d expects (batch, features, seq_len).
        return self.network(x.transpose(1, 2))
