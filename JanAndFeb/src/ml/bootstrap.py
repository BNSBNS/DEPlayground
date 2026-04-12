"""Module-wide wiring: register model strategies and build services.

This is the single place that knows *all* of the concrete ForecastModel
implementations. Everywhere else in the codebase depends only on the
``ForecastModel`` port and asks the ``ModelRegistry`` by name.

Keeping registration out of module ``__init__.py`` means importing
``src.ml.models`` has no side effects — tests can install a subset of
the strategies without dragging in statsmodels / lightgbm / torch.
"""

from __future__ import annotations

from typing import Any

from src.ml.models.classical.arima import SARIMAXForecaster
from src.ml.models.deep.adapter import NeuralForecastAdapter
from src.ml.models.deep.cnn import CNNForecaster
from src.ml.models.deep.gru import GRUForecaster
from src.ml.models.deep.mlp import MLPForecaster
from src.ml.models.gradient.lightgbm_model import LightGBMForecaster
from src.ml.models.registry import ModelRegistry, registry


def _neural_factory(net_cls: type) -> Any:
    """Build a factory that wraps a neural net in the adapter."""

    def factory(**kwargs: Any) -> NeuralForecastAdapter:
        hparams = kwargs.pop("hparams", None) or {
            "hidden_size": kwargs.pop("hidden_size", 64),
            "num_layers": kwargs.pop("num_layers", 2),
            "dropout": kwargs.pop("dropout", 0.1),
            "seq_len": kwargs.pop("seq_len", 60),
            "horizon": kwargs.pop("horizon", 15),
        }
        return NeuralForecastAdapter(
            net_cls=net_cls,
            hparams=hparams,
            symbol=kwargs.pop("symbol", "UNKNOWN"),
            epochs=kwargs.pop("epochs", 50),
            batch_size=kwargs.pop("batch_size", 64),
            learning_rate=kwargs.pop("learning_rate", 1e-3),
            patience=kwargs.pop("patience", 5),
        )

    return factory


def register_models(target: ModelRegistry = registry) -> ModelRegistry:
    """Idempotently register the five default strategies."""
    factories: dict[str, Any] = {
        "sarimax": SARIMAXForecaster,
        "lightgbm": LightGBMForecaster,
        "mlp": _neural_factory(MLPForecaster),
        "gru": _neural_factory(GRUForecaster),
        "cnn": _neural_factory(CNNForecaster),
    }
    for name, factory in factories.items():
        if name not in target.names():
            target.register(name, factory)
    return target


class _NeuralLoader:
    """Thin shim that binds a neural network class to the adapter loader.

    ``InferenceService`` calls ``loader.load(store, uri)`` with two arguments,
    but :meth:`NeuralForecastAdapter.load` needs a third ``net_cls`` to know
    which architecture to rebuild. This shim captures that binding.
    """

    def __init__(self, net_cls: type) -> None:
        self._net_cls = net_cls

    def load(self, store: Any, uri: str) -> NeuralForecastAdapter:
        return NeuralForecastAdapter.load(store, uri, net_cls=self._net_cls)


#: Map model name -> loader used by ``InferenceService`` to reconstruct
#: persisted artifacts. Classical and gradient models load through their own
#: classes; neural models go through a bound :class:`_NeuralLoader`.
MODEL_LOADERS: dict[str, Any] = {
    "sarimax": SARIMAXForecaster,
    "lightgbm": LightGBMForecaster,
    "mlp": _NeuralLoader(MLPForecaster),
    "gru": _NeuralLoader(GRUForecaster),
    "cnn": _NeuralLoader(CNNForecaster),
}
