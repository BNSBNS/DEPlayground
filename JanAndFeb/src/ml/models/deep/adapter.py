"""Adapter between the ``ForecastModel`` port (pandas) and ``BaseNeuralForecaster`` (tensors).

This is where "pandas world" and "tensor world" meet. The trainer hands us
a DataFrame + Series of floats; we:

    1. Normalize the feature matrix (mean/std stored for inference)
    2. Build a ``SlidingWindowDataset`` from the arrays
    3. Split 80/20 chronologically into train/val loaders
    4. Call ``BaseNeuralForecaster.fit_loader``
    5. At predict time, slice the last ``seq_len`` rows and run one forward pass
    6. Turn the resulting tensor back into a ``ForecastBatch``

The adapter is ``ForecastModel`` — the inner net is deliberately NOT. Keeps
PyTorch code out of the domain layer and vice versa.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from src.common.logging_config import get_logger
from src.ml.domain.models import Forecast, ForecastBatch, ModelMetadata
from src.ml.models.deep.datasets import SlidingWindowDataset

if TYPE_CHECKING:
    from src.ml.domain.ports import ModelStore
    from src.ml.models.deep.base import BaseNeuralForecaster

logger = get_logger(__name__)


class NeuralForecastAdapter:
    """Wraps any ``BaseNeuralForecaster`` as a ``ForecastModel``."""

    def __init__(
        self,
        net_cls: type[BaseNeuralForecaster],
        hparams: dict[str, Any],
        symbol: str = "UNKNOWN",
        version: str | None = None,
        epochs: int = 50,
        batch_size: int = 64,
        learning_rate: float = 1e-3,
        patience: int = 5,
    ) -> None:
        self._net_cls = net_cls
        self._hparams = dict(hparams)
        self.name = net_cls.name
        self.symbol = symbol
        self.version = version or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._epochs = epochs
        self._batch_size = batch_size
        self._learning_rate = learning_rate
        self._patience = patience

        self._net: BaseNeuralForecaster | None = None
        self._feature_columns: list[str] = []
        self._feature_hash: str = ""
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None

    # ------------------------------------------------------------------
    # ForecastModel.fit
    # ------------------------------------------------------------------
    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series[float],
    ) -> ModelMetadata:
        self._feature_columns = list(features.columns)
        self._feature_hash = getattr(features, "attrs", {}).get("feature_hash", "")

        x = features.astype(float).values
        y = target.astype(float).values

        # Standardize features (critical for neural training stability).
        self._mean = x.mean(axis=0)
        self._std = x.std(axis=0)
        self._std = np.where(self._std < 1e-8, 1.0, self._std)
        x_norm = (x - self._mean) / self._std

        seq_len = int(self._hparams["seq_len"])
        horizon = int(self._hparams["horizon"])

        # Complete the hparams with the actual input size.
        self._hparams["input_size"] = x_norm.shape[1]
        self._net = self._net_cls(hparams=self._hparams)

        full = SlidingWindowDataset(x_norm, np.asarray(y), seq_len=seq_len, horizon=horizon)

        # Chronological 80/20 split — no shuffling (time series!).
        split_idx = int(len(full) * 0.8)
        train_ds = torch.utils.data.Subset(full, range(split_idx))
        val_ds = torch.utils.data.Subset(full, range(split_idx, len(full)))

        train_loader: DataLoader[Any] = DataLoader(
            train_ds, batch_size=self._batch_size, shuffle=True
        )
        val_loader: DataLoader[Any] | None = (
            DataLoader(val_ds, batch_size=self._batch_size, shuffle=False)
            if len(val_ds) > 0
            else None
        )

        metrics = self._net.fit_loader(
            train_loader,
            val_loader,
            epochs=self._epochs,
            learning_rate=self._learning_rate,
            patience=self._patience,
        )

        return ModelMetadata(
            model_name=self.name,
            model_version=self.version,
            trained_at=datetime.now(UTC),
            metrics=metrics,
            params={
                **self._hparams,
                "symbol": self.symbol,
                "epochs": self._epochs,
                "batch_size": self._batch_size,
                "learning_rate": self._learning_rate,
            },
            artifact_uri="pending",
        )

    # ------------------------------------------------------------------
    # ForecastModel.predict
    # ------------------------------------------------------------------
    def predict(
        self,
        features: pd.DataFrame,
        horizon: int,  # noqa: ARG002 - horizon is fixed by the trained network
    ) -> ForecastBatch:
        if self._net is None or self._mean is None or self._std is None:
            raise RuntimeError("Neural forecaster must be fit before predict().")

        seq_len = int(self._hparams["seq_len"])
        trained_horizon = int(self._hparams["horizon"])

        x = features[self._feature_columns].astype(float).values
        if len(x) < seq_len:
            raise ValueError(f"Need at least {seq_len} rows for inference, got {len(x)}")

        x_norm = (x[-seq_len:] - self._mean) / self._std
        x_tensor = torch.from_numpy(x_norm.astype(np.float32)).unsqueeze(0)
        y_hat = self._net.predict_tensor(x_tensor).squeeze(0).numpy()

        last_ts = self._last_timestamp(features)
        generated_at = datetime.now(UTC)

        forecasts = [
            Forecast(
                symbol=self.symbol,
                forecast_for=last_ts + timedelta(minutes=i + 1),
                generated_at=generated_at,
                horizon_minutes=i + 1,
                yhat=Decimal(str(round(float(y_hat[i]), 8))),
                yhat_lower=None,
                yhat_upper=None,
                model_name=self.name,
                model_version=self.version,
                feature_hash=self._feature_hash or f"{self.name}-features",
            )
            for i in range(trained_horizon)
        ]
        return ForecastBatch(forecasts=forecasts)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, store: ModelStore) -> str:
        if self._net is None:
            raise RuntimeError("Cannot save an unfitted model.")

        # Bundle the net's state dict together with the adapter-level state
        # (scaler stats, feature columns) into one artifact.
        buf = io.BytesIO()
        torch.save(
            {
                "net_state_dict": self._net.state_dict(),
                "hparams": self._hparams,
                "feature_columns": self._feature_columns,
                "mean": self._mean,
                "std": self._std,
            },
            buf,
        )

        metadata: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "symbol": self.symbol,
            "hparams": self._hparams,
            "feature_hash": self._feature_hash,
            "feature_columns": self._feature_columns,
            "net_cls": self._net_cls.__name__,
        }
        return store.save(self.name, self.version, buf.getvalue(), metadata)

    @classmethod
    def load(
        cls,
        store: ModelStore,
        uri: str,
        net_cls: type[BaseNeuralForecaster],
    ) -> NeuralForecastAdapter:
        artifact, metadata = store.load(uri)
        adapter = cls(
            net_cls=net_cls,
            hparams=metadata["hparams"],
            symbol=metadata["symbol"],
            version=metadata["version"],
        )
        payload = torch.load(io.BytesIO(artifact), weights_only=False)
        adapter._net = net_cls(hparams=payload["hparams"])
        adapter._net.load_state_dict(payload["net_state_dict"])
        adapter._feature_columns = payload["feature_columns"]
        adapter._mean = payload["mean"]
        adapter._std = payload["std"]
        adapter._feature_hash = metadata.get("feature_hash", "")
        return adapter

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _last_timestamp(features: pd.DataFrame) -> datetime:
        if isinstance(features.index, pd.DatetimeIndex) and len(features.index):
            ts = features.index[-1]
            return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        return datetime.now(UTC)
