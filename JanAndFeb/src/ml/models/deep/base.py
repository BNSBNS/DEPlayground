"""Template Method base class for neural forecasters.

This is where the entire PyTorch training loop lives. Subclasses override
only ``build_network`` and ``forward``; everything else — device placement,
optimizer, loss, per-epoch tracking, early stopping, checkpoint save/load —
is inherited for free.

This matches the architectural pattern used by PyTorch Lightning's
``LightningModule``, Keras' ``Model.fit``, and ``pytorch-forecasting``'s
``BaseModel``. The point is that every child (GRU, CNN, MLP) ends up being
a 20-30 line file containing only its distinguishing architecture.
"""

from __future__ import annotations

import copy
import io
import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import torch
from torch import nn

from src.common.logging_config import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from torch.utils.data import DataLoader

logger = get_logger(__name__)


class BaseNeuralForecaster(nn.Module, ABC):
    """Abstract base class: children only provide the network architecture.

    The ``hparams`` dict holds everything a child might need to build its
    network (``input_size``, ``hidden_size``, ``num_layers``, ``dropout``,
    ``horizon``, ``seq_len``). Training hyperparameters (``lr``, ``epochs``,
    ``batch_size``, ``patience``) are passed to ``fit`` at runtime so the
    same instance can be reused with different training budgets.
    """

    #: Unique identifier the child sets. Used for logging and model registry.
    name: str = "base-neural"

    def __init__(self, hparams: dict[str, Any]) -> None:
        super().__init__()
        self.hparams: dict[str, Any] = dict(hparams)
        # build_network may use self.hparams — call it last.
        self.network: nn.Module = self.build_network()

    # ==================================================================
    # Abstract hooks — children must implement these
    # ==================================================================
    @abstractmethod
    def build_network(self) -> nn.Module:
        """Return the nn.Module that ``forward`` will call."""

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        """Forward pass. Input shape: ``(batch, seq_len, features)``."""

    # ==================================================================
    # Shared invariant logic
    # ==================================================================
    def fit_loader(
        self,
        train_loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
        val_loader: DataLoader[tuple[torch.Tensor, torch.Tensor]] | None = None,
        epochs: int = 50,
        learning_rate: float = 1e-3,
        patience: int = 5,
    ) -> dict[str, float]:
        """Run the full training loop and return final metrics.

        Args:
            train_loader: yields ``(x, y)`` batches.
            val_loader: optional held-out loader for early stopping.
            epochs: maximum epochs.
            learning_rate: Adam learning rate.
            patience: stop if val loss hasn't improved in this many epochs.

        Returns:
            Dict of ``{"train_loss": ..., "val_loss": ...}`` from the best epoch.
        """
        device = _pick_device()
        self.to(device)

        optimizer = torch.optim.Adam(self.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()

        best_val = float("inf")
        best_state: dict[str, torch.Tensor] | None = None
        patience_counter = 0
        final_train_loss = float("nan")

        for epoch in range(1, epochs + 1):
            train_loss = self._train_one_epoch(train_loader, optimizer, criterion, device)
            final_train_loss = train_loss

            if val_loader is not None:
                val_loss = self._evaluate(val_loader, criterion, device)
                logger.debug(
                    "Neural epoch",
                    name=self.name,
                    epoch=epoch,
                    train_loss=train_loss,
                    val_loss=val_loss,
                )
                if val_loss < best_val - 1e-6:
                    best_val = val_loss
                    best_state = copy.deepcopy(self.state_dict())
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        logger.info(
                            "Early stopping",
                            name=self.name,
                            epoch=epoch,
                            best_val=best_val,
                        )
                        break
            else:
                logger.debug("Neural epoch", name=self.name, epoch=epoch, train_loss=train_loss)

        if best_state is not None:
            self.load_state_dict(best_state)

        return {
            "train_loss": float(final_train_loss),
            "val_loss": float(best_val) if best_val != float("inf") else float("nan"),
        }

    def predict_tensor(self, x: torch.Tensor) -> torch.Tensor:
        """Run a single forward pass in eval mode and return CPU tensor."""
        device = _pick_device()
        self.to(device)
        self.eval()
        with torch.no_grad():
            out = self(x.to(device))
        return out.detach().cpu()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_bytes(self) -> bytes:
        """Serialize weights + hparams to a single bytes blob (for ModelStore)."""
        buf = io.BytesIO()
        torch.save(
            {"state_dict": self.state_dict(), "hparams": self.hparams},
            buf,
        )
        return buf.getvalue()

    @classmethod
    def load_bytes(cls, payload: bytes) -> BaseNeuralForecaster:
        """Rehydrate an instance from bytes produced by ``save_bytes``."""
        buf = io.BytesIO(payload)
        blob = torch.load(buf, weights_only=False)
        instance = cls(hparams=blob["hparams"])
        instance.load_state_dict(blob["state_dict"])
        return instance

    def save_to_disk(self, path: Path) -> None:
        """Convenience helper — useful for notebook debugging, not the main path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.save_bytes())
        (path.with_suffix(".json")).write_text(
            json.dumps(self.hparams, indent=2, default=str),
            encoding="utf-8",
        )

    # ==================================================================
    # Private helpers
    # ==================================================================
    def _train_one_epoch(
        self,
        loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
        optimizer: torch.optim.Optimizer,
        criterion: nn.Module,
        device: torch.device,
    ) -> float:
        self.train()
        total = 0.0
        count = 0
        for x_batch, y_batch in loader:
            x_dev = x_batch.to(device)
            y_dev = y_batch.to(device)
            optimizer.zero_grad()
            pred = self(x_dev)
            loss = criterion(pred, y_dev)
            loss.backward()
            optimizer.step()
            total += float(loss.item()) * len(x_dev)
            count += len(x_dev)
        return total / max(count, 1)

    def _evaluate(
        self,
        loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
        criterion: nn.Module,
        device: torch.device,
    ) -> float:
        self.eval()
        total = 0.0
        count = 0
        with torch.no_grad():
            for x_batch, y_batch in loader:
                x_dev = x_batch.to(device)
                y_dev = y_batch.to(device)
                pred = self(x_dev)
                loss = criterion(pred, y_dev)
                total += float(loss.item()) * len(x_dev)
                count += len(x_dev)
        return total / max(count, 1)


def _pick_device() -> torch.device:
    """Auto-select GPU if available, else CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
