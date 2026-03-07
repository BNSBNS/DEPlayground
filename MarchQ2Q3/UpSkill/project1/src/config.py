"""Configuration management using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """PostgreSQL connection configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    user: str = Field(default="observability")
    password: str = Field(default="observability")
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    db: str = Field(default="observability")
    dsn: str | None = Field(default=None)
    pool_min: int = Field(default=2, ge=1, le=20)
    pool_max: int = Field(default=10, ge=1, le=50)

    def get_dsn(self) -> str:
        """Build PostgreSQL DSN from components or return explicit DSN."""
        if self.dsn:
            return self.dsn
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @field_validator("dsn", mode="before")
    @classmethod
    def validate_dsn(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DSN must start with postgresql:// or postgres://")
        return v


class DetectorSettings(BaseSettings):
    """Default thresholds for data quality detectors."""

    model_config = SettingsConfigDict(extra="ignore")

    freshness_warning_minutes: int = Field(default=60, ge=1)
    freshness_critical_minutes: int = Field(default=120, ge=1)
    volume_lookback_days: int = Field(default=14, ge=3)
    volume_warning_zscore: float = Field(default=2.0, ge=0.5)
    volume_critical_zscore: float = Field(default=3.0, ge=1.0)
    distribution_warning_pvalue: float = Field(default=0.05, ge=0.001, le=1.0)
    distribution_critical_pvalue: float = Field(default=0.01, ge=0.001, le=1.0)


class RCASettings(BaseSettings):
    """Root cause analysis configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    correlation_window_minutes: int = Field(default=30, ge=5)
    base_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    confidence_increment: float = Field(default=0.1, ge=0.0, le=0.5)
    max_confidence: float = Field(default=0.95, ge=0.5, le=1.0)


class AlertingSettings(BaseSettings):
    """Alerting configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    slack_webhook_url: str | None = Field(default=None)
    enabled: bool = Field(default=False)


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore")

    port: int = Field(default=8010, ge=1024, le=65535)
    cors_origins: list[str] = Field(
        default=["http://localhost:3010", "http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return ["http://localhost:3010"]


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    detectors: DetectorSettings = Field(default_factory=DetectorSettings)
    rca: RCASettings = Field(default_factory=RCASettings)
    alerting: AlertingSettings = Field(default_factory=AlertingSettings)
    api: APISettings = Field(default_factory=APISettings)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_json_format: bool = Field(default=False)
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    debug: bool = Field(default=False)
    simulation_mode: bool = Field(default=False)

    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
