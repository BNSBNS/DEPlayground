from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    user: str = "streaming"
    password: str = "streaming"
    db: str = "streaming_analytics"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:19092"
    consumer_group: str = "streaming-analytics"


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_")

    port: int = 8040
    cors_origins: list[str] = Field(
        default=["http://localhost:3040", "http://localhost:8040"]
    )
    ws_enabled: bool = Field(default=True, alias="WS_ENABLED")


class SimulationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIMULATION_")

    events_per_second: int = Field(default=50, alias="EVENTS_PER_SECOND")
    scenario: str = "normal"


class SchemaRegistrySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCHEMA_REGISTRY_")

    url: str = "http://localhost:18081"


class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    kafka: KafkaSettings = KafkaSettings()
    api: APISettings = APISettings()
    simulation: SimulationSettings = SimulationSettings()
    schema_registry: SchemaRegistrySettings = SchemaRegistrySettings()


settings = Settings()
