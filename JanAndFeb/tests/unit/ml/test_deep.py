"""Unit tests for the deep-learning layer.

Exercises the Template Method base, all three children, the adapter, and
the sliding-window dataset. Uses tiny hyperparameters so the whole test
module runs in <10 seconds on CPU.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from src.ml.features.builder import FeatureBuilder
from src.ml.models.deep.adapter import NeuralForecastAdapter
from src.ml.models.deep.cnn import CNNForecaster
from src.ml.models.deep.datasets import SlidingWindowDataset
from src.ml.models.deep.gru import GRUForecaster
from src.ml.models.deep.mlp import MLPForecaster
from src.ml.store.filesystem import FilesystemModelStore

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd

    from src.ml.models.deep.base import BaseNeuralForecaster


def _tiny_hparams(input_size: int = 3) -> dict[str, Any]:
    return {
        "input_size": input_size,
        "hidden_size": 8,
        "num_layers": 1,
        "dropout": 0.0,
        "seq_len": 12,
        "horizon": 3,
    }


# ----------------------------- datasets -----------------------------------
def test_sliding_window_shapes() -> None:
    features = np.random.default_rng(0).standard_normal((50, 4)).astype(np.float32)
    target = np.random.default_rng(1).standard_normal(50).astype(np.float32)
    ds = SlidingWindowDataset(features, target, seq_len=10, horizon=3)
    assert len(ds) == 50 - 10 - 3 + 1

    x, y = ds[0]
    assert x.shape == (10, 4)
    assert y.shape == (3,)


def test_sliding_window_rejects_too_short() -> None:
    with pytest.raises(ValueError, match="Need at least"):
        SlidingWindowDataset(
            np.zeros((5, 2), dtype=np.float32),
            np.zeros(5, dtype=np.float32),
            seq_len=10,
            horizon=3,
        )


# --------------------------- children build -------------------------------
@pytest.mark.parametrize("cls", [MLPForecaster, GRUForecaster, CNNForecaster])
def test_child_forward_shape(cls: type[BaseNeuralForecaster]) -> None:
    hparams = _tiny_hparams()
    net = cls(hparams=hparams)
    x = torch.zeros(4, hparams["seq_len"], hparams["input_size"])
    out = net(x)
    assert out.shape == (4, hparams["horizon"])


# ------------------------ full fit loop -----------------------------------
def test_base_fit_loop_converges() -> None:
    """A tiny MLP should reduce training loss on a learnable sine wave."""
    np.random.default_rng(42)
    n = 200
    t = np.arange(n, dtype=np.float32)
    series = np.sin(2 * np.pi * t / 20).astype(np.float32)
    features = np.stack([series, np.cos(2 * np.pi * t / 20)], axis=1).astype(np.float32)

    ds = SlidingWindowDataset(features, series, seq_len=12, horizon=3)
    loader: DataLoader[Any] = DataLoader(ds, batch_size=8, shuffle=True)

    hparams = {
        "input_size": 2,
        "hidden_size": 16,
        "num_layers": 1,
        "dropout": 0.0,
        "seq_len": 12,
        "horizon": 3,
    }
    net = MLPForecaster(hparams=hparams)

    initial = _batch_loss(net, ds)
    net.fit_loader(loader, val_loader=None, epochs=30, learning_rate=1e-2, patience=5)
    final = _batch_loss(net, ds)
    assert final < initial * 0.5


def _batch_loss(net: BaseNeuralForecaster, ds: SlidingWindowDataset) -> float:
    net.eval()
    xs = torch.stack([ds[i][0] for i in range(len(ds))])
    ys = torch.stack([ds[i][1] for i in range(len(ds))])
    with torch.no_grad():
        return float(torch.nn.functional.mse_loss(net(xs), ys).item())


# ---------------------- adapter end-to-end --------------------------------
def test_adapter_fit_predict_save_load(raw_aggregates: pd.DataFrame, tmp_path: Path) -> None:
    ff = FeatureBuilder().build(raw_aggregates)
    store = FilesystemModelStore(tmp_path)

    hparams = {
        "hidden_size": 16,
        "num_layers": 1,
        "dropout": 0.0,
        "seq_len": 20,
        "horizon": 5,
    }
    adapter = NeuralForecastAdapter(
        net_cls=MLPForecaster,
        hparams=hparams,
        symbol="POWER_DE",
        epochs=3,
        batch_size=16,
        learning_rate=1e-2,
        patience=2,
    )

    meta = adapter.fit(ff.x, ff.y)
    assert meta.model_name == "mlp"
    assert "train_loss" in meta.metrics

    batch = adapter.predict(ff.x, horizon=5)
    assert len(batch) == 5

    uri = adapter.save(store)
    loaded = NeuralForecastAdapter.load(store, uri, net_cls=MLPForecaster)
    loaded_batch = loaded.predict(ff.x, horizon=5)
    # Predictions should be numerically identical across save/load.
    for a, b in zip(batch.forecasts, loaded_batch.forecasts, strict=True):
        assert a.yhat == b.yhat
