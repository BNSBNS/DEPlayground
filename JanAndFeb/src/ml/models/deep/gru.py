"""GRU forecaster — recurrence.

A Gated Recurrent Unit reads the input sequence one timestep at a time and
maintains an internal hidden state that summarizes what it has seen so far.
At the end of the sequence the final hidden state is fed through a linear
head to produce the horizon-length forecast.

Compared to LSTM, GRU has one fewer gate and slightly fewer parameters but
near-identical accuracy on time-series tasks — the usual learning
recommendation.
"""

from __future__ import annotations

import torch
from torch import nn

from src.ml.models.deep.base import BaseNeuralForecaster


class GRUForecaster(BaseNeuralForecaster):
    """Multi-layer GRU followed by a linear head on the last hidden state."""

    name = "gru"

    def build_network(self) -> nn.Module:
        num_layers = int(self.hparams["num_layers"])
        dropout = float(self.hparams["dropout"]) if num_layers > 1 else 0.0
        return nn.ModuleDict(
            {
                "gru": nn.GRU(
                    input_size=self.hparams["input_size"],
                    hidden_size=self.hparams["hidden_size"],
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout,
                ),
                "head": nn.Linear(self.hparams["hidden_size"], self.hparams["horizon"]),
            }
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        # Input shape: (batch, seq_len, features).
        out, _ = self.network["gru"](x)
        last_step = out[:, -1, :]  # shape: (batch, hidden_size)
        return self.network["head"](last_step)
