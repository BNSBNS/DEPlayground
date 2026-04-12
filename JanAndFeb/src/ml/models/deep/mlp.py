"""MLP forecaster — the dumb baseline you must beat.

Flattens the sliding window and feeds it into a 2-layer dense network.
Provides exactly nothing beyond what a feed-forward network can do, which is
why it's the industry-standard sanity check: if your GRU / CNN / Transformer
can't beat this on a held-out set, something is wrong.
"""

from __future__ import annotations

import torch
from torch import nn

from src.ml.models.deep.base import BaseNeuralForecaster


class MLPForecaster(BaseNeuralForecaster):
    """Flatten-then-Linear baseline."""

    name = "mlp"

    def build_network(self) -> nn.Module:
        flat_size = self.hparams["seq_len"] * self.hparams["input_size"]
        return nn.Sequential(
            nn.Flatten(),
            nn.Linear(flat_size, self.hparams["hidden_size"]),
            nn.ReLU(),
            nn.Dropout(self.hparams["dropout"]),
            nn.Linear(self.hparams["hidden_size"], self.hparams["horizon"]),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        # x: (batch, seq_len, features) -> Flatten handles the reshape.
        return self.network(x)
