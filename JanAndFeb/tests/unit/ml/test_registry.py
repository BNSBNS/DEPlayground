"""Unit tests for the ModelRegistry."""

from __future__ import annotations

from typing import Any

import pytest

from src.ml.models.registry import ModelRegistry


class _FakeModel:
    name = "fake"
    version = "0.0.1"

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_register_and_create() -> None:
    reg = ModelRegistry()
    reg.register("fake", _FakeModel)
    model = reg.create("fake", hidden=32)
    assert isinstance(model, _FakeModel)
    assert model.kwargs == {"hidden": 32}


def test_duplicate_register_raises() -> None:
    reg = ModelRegistry()
    reg.register("fake", _FakeModel)
    with pytest.raises(ValueError, match="already registered"):
        reg.register("fake", _FakeModel)


def test_unknown_name_raises() -> None:
    reg = ModelRegistry()
    with pytest.raises(KeyError, match="Unknown model"):
        reg.create("ghost")


def test_names_sorted() -> None:
    reg = ModelRegistry()
    reg.register("b", _FakeModel)
    reg.register("a", _FakeModel)
    assert reg.names() == ["a", "b"]
