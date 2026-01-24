"""Configuration management using pydantic-settings.

This module provides centralized configuration with validation for all services.
Configuration is loaded from environment variables following 12-factor app principles.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class KafkaSettings(BaseSettings):
    """Kafka connection and topic configuration."""

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_",
        extra="ignore",
    )

    bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Comma-separated list of Kafka broker addresses",
    )
    topic: str = Field(
        default="trades",
        description="Main topic for trade events",
    )
    dlq_topic: str = Field(
        default="trades-dlq",
        description="Dead Letter Queue topic for failed messages",
    )
    consumer_group: str = Field(
        default="trade-aggregator",
        description="Consumer group ID for the streaming consumer",
    )

    # Producer settings (hardcoded for trading durability requirements)
    # These are documented here but set in kafka_utils.py
    # acks: all (wait for all replicas)
    # enable.idempotence: true (exactly-once producer semantics)

    @field_validator("bootstrap_servers")
    @classmethod
    def validate_bootstrap_servers(cls, v: str) -> str:
        """Validate bootstrap servers format."""
        if not v or not v.strip():
            raise ValueError("bootstrap_servers cannot be empty")
        return v


class PostgresSettings(BaseSettings):
    """PostgreSQL connection configuration."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        extra="ignore",
    )

    user: str = Field(default="trading")
    password: str = Field(default="trading")
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    db: str = Field(default="trades")

    # Alternative: full DSN (takes precedence if set)
    dsn: str | None = Field(
        default=None,
        description="Full PostgreSQL connection string (overrides individual settings)",
    )

    def get_dsn(self) -> str:
        """Get the PostgreSQL connection string.

        Returns the explicitly set DSN if provided, otherwise constructs
        one from the individual connection parameters.
        """
        if self.dsn:
            return self.dsn
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @field_validator("dsn", mode="before")
    @classmethod
    def validate_dsn(cls, v: str | None) -> str | None:
        """Validate DSN format if provided."""
        if v is None or v == "":
            return None
        # Basic validation - pydantic PostgresDsn would be stricter
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DSN must start with postgresql:// or postgres://")
        return v


class ProducerSettings(BaseSettings):
    """Trade producer configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PRODUCER_",
        extra="ignore",
    )

    rate: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Events per second (normal rate)",
    )
    burst_enabled: bool = Field(
        default=True,
        description="Enable burst mode to simulate market volatility",
    )
    burst_multiplier: int = Field(
        default=5,
        ge=2,
        le=100,
        description="Rate multiplier during burst periods",
    )
    burst_duration: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Burst duration in seconds",
    )
    burst_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time between bursts in seconds",
    )


class ConsumerSettings(BaseSettings):
    """Streaming consumer configuration."""

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )

    window_duration_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Tumbling window duration in seconds",
    )
    late_event_grace_seconds: int = Field(
        default=30,
        ge=0,
        le=300,
        description="Grace period for late-arriving events",
    )
    db_batch_size: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum batch size for database writes",
    )


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="API_",
        extra="ignore",
    )

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins. Use ['*'] only in development.",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS requests",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


class Settings(BaseSettings):
    """Main application settings.

    Aggregates all configuration sections and provides application-wide settings.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        env_nested_delimiter="__",
    )

    # Nested configuration sections
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    producer: ProducerSettings = Field(default_factory=ProducerSettings)
    consumer: ConsumerSettings = Field(default_factory=ConsumerSettings)
    api: APISettings = Field(default_factory=APISettings)

    # Application-wide settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_json_format: bool = Field(
        default=False,
        description="Use JSON format for logs (recommended for production)",
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Runtime environment",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Uses lru_cache to ensure settings are loaded once and reused.
    This is the recommended way to access settings throughout the application.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
