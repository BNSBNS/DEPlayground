"""Shared test fixtures for SecurityDataPipeline."""

from __future__ import annotations

import pytest

from src.config import GeneratorSettings
from src.data.generator import LogEvent, LogGenerator


@pytest.fixture()
def generator_settings() -> GeneratorSettings:
    """Small dataset settings for fast tests."""
    return GeneratorSettings(num_events=1000, seed=42, num_users=20, num_hosts=10)


@pytest.fixture()
def generator(generator_settings: GeneratorSettings) -> LogGenerator:
    """Log generator with test settings."""
    return LogGenerator(generator_settings)


@pytest.fixture()
def events(generator: LogGenerator) -> list[LogEvent]:
    """Generated log events (1K)."""
    return generator.generate()
