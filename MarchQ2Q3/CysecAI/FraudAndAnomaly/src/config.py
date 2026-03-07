"""Configuration for Fraud & Anomaly Detection Engine."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cysec_shared.config import BaseProjectSettings


class GeneratorSettings(BaseSettings):
    """Synthetic data generator configuration."""

    model_config = SettingsConfigDict(env_prefix="GENERATOR_", extra="ignore")

    num_transactions: int = Field(default=100_000, ge=1000)
    fraud_rate: float = Field(default=0.03, ge=0.01, le=0.20)
    num_users: int = Field(default=5000, ge=100)
    num_merchants: int = Field(default=200, ge=10)
    seed: int = Field(default=42)


class FraudSettings(BaseProjectSettings):
    """Main application settings for Fraud & Anomaly Detection Engine."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    generator: GeneratorSettings = Field(default_factory=GeneratorSettings)
    api_port: int = Field(default=8101, ge=1024, le=65535)
    api_key: str = Field(default="changeme")


@lru_cache
def get_settings() -> FraudSettings:
    """Get cached application settings."""
    return FraudSettings()
