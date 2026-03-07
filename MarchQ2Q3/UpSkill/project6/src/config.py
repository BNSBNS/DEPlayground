from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    db: str = "feature_store"
    user: str = "feature_store"
    password: str = "feature_store"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6380
    db: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9093"
    consumer_group: str = "feature-store-consumer"


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_")

    port: int = 8060


class BatchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BATCH_")

    schedule_minutes: int = 60
    backfill_days: int = 90


class StreamSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STREAM_")

    enabled: bool = True
    window_bucket_ttl_seconds: int = 7200  # Redis key TTL for stream aggregation windows


class MonitoringSettings(BaseSettings):
    """Drift detection thresholds — tune via MONITORING_* environment variables.

    PSI (Population Stability Index) for numeric features:
      < psi_warning            → no drift
      psi_warning..psi_critical → warning
      >= psi_critical           → critical

    Chi-squared for categorical features:
      p_value < chi2_p_threshold → drift detected
    """

    model_config = SettingsConfigDict(env_prefix="MONITORING_")

    psi_warning: float = 0.1
    psi_critical: float = 0.2
    chi2_p_threshold: float = 0.05


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.example", env_file_encoding="utf-8")

    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    api: APISettings = Field(default_factory=APISettings)
    batch: BatchSettings = Field(default_factory=BatchSettings)
    stream: StreamSettings = Field(default_factory=StreamSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)


def get_settings() -> Settings:
    return Settings()
