"""Base configuration patterns for CysecAI projects.

Every project extends BaseProjectSettings with project-specific fields.
Pattern mirrors UpSkill/project1/src/config.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseSettings):
    """Kafka connection config shared across alert producers/consumers."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_", extra="ignore")

    bootstrap_servers: str = Field(default="localhost:9092")
    alerts_topic: str = Field(default="cysec.alerts")
    group_id: str = Field(default="cysec-default")


class BaseProjectSettings(BaseSettings):
    """Base settings that every CysecAI project extends.

    Provides shared config: Kafka, logging, environment.
    Projects add their own fields via subclass.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_json_format: bool = Field(default=False)
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    debug: bool = Field(default=False)

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
