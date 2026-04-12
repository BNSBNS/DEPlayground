"""Model factory registry — resolves a model name to a constructor callable.

Each adapter module registers its own factory at import time via the module
level ``registry.register(name, factory)`` call. The trainer, API, and CLI
then only ever speak in string names, which keeps config files and command
line arguments clean.

Usage::

    from src.ml.models.registry import registry
    model = registry.create("lightgbm", hparams={...})
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.ml.domain.ports import ForecastModel

ModelFactory = Callable[..., ForecastModel]


class ModelRegistry:
    """A tiny name-to-factory map with friendly errors."""

    def __init__(self) -> None:
        self._factories: dict[str, ModelFactory] = {}

    def register(self, name: str, factory: ModelFactory) -> None:
        if name in self._factories:
            raise ValueError(f"Model '{name}' already registered.")
        self._factories[name] = factory

    def create(self, name: str, **kwargs: Any) -> ForecastModel:
        try:
            factory = self._factories[name]
        except KeyError as err:
            available = ", ".join(sorted(self._factories)) or "<none>"
            raise KeyError(f"Unknown model '{name}'. Registered models: {available}") from err
        return factory(**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)


#: Singleton used across the module. Import and register with:
#:     from src.ml.models.registry import registry
#:     registry.register("lightgbm", LightGBMForecaster)
registry = ModelRegistry()
