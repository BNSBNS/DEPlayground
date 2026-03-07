"""Configuration management using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """PostgreSQL + pgvector connection configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    user: str = Field(default="graphrag")
    password: str = Field(default="graphrag")
    db: str = Field(default="graphrag")
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


class MemgraphSettings(BaseSettings):
    """Memgraph connection configuration (bolt protocol)."""

    model_config = SettingsConfigDict(env_prefix="MEMGRAPH_", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=7688, ge=1, le=65535)
    user: str = Field(default="")
    password: str = Field(default="")

    def get_uri(self) -> str:
        """Build bolt URI for Memgraph."""
        return f"bolt://{self.host}:{self.port}"


class EmbeddingSettings(BaseSettings):
    """Sentence embedding model configuration."""

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", extra="ignore")

    model_name: str = Field(default="all-MiniLM-L6-v2")
    dimension: int = Field(default=384, ge=1)
    chunk_size: int = Field(default=512, ge=64)
    chunk_overlap: int = Field(default=50, ge=0)


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    provider: Literal["ollama", "anthropic", "openai"] = Field(default="ollama")
    model: str = Field(default="llama3.2")
    base_url: str = Field(default="http://localhost:11434")
    api_key: str = Field(default="")
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore")

    port: int = Field(default=8020, ge=1024, le=65535)
    cors_origins: list[str] = Field(default=["*"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return ["*"]


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    memgraph: MemgraphSettings = Field(default_factory=MemgraphSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    api: APISettings = Field(default_factory=APISettings)

    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_json_format: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
