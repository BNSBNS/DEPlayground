"""Shared test fixtures for Fraud & Anomaly Detection Engine."""

from __future__ import annotations

import pytest

from src.config import GeneratorSettings
from src.data.generator import Transaction, TransactionGenerator


@pytest.fixture
def generator_settings() -> GeneratorSettings:
    """Small dataset settings for fast tests."""
    return GeneratorSettings(
        num_transactions=1000,
        fraud_rate=0.03,
        num_users=100,
        num_merchants=15,
        seed=42,
    )


@pytest.fixture
def generator(generator_settings: GeneratorSettings) -> TransactionGenerator:
    """Configured transaction generator."""
    return TransactionGenerator(generator_settings)


@pytest.fixture
def sample_transactions(generator: TransactionGenerator) -> list[Transaction]:
    """Pre-generated transaction dataset (1K records)."""
    return generator.generate()
