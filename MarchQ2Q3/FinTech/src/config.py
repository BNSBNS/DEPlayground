"""Centralized configuration via environment variables (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATA_SOURCE: Literal["mock", "live"] = "mock"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    FRED_API_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./data/embeddings"
    DATA_DIR: str = "./data"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False
    ENVIRONMENT: Literal["dev", "staging", "prod"] = "dev"
    API_KEY: str = "dev-key"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8501"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
