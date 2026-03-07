"""TIKG project configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jSettings(BaseSettings):
    """Neo4j connection settings."""

    model_config = SettingsConfigDict(env_prefix="NEO4J_", extra="ignore")

    uri: str = Field(default="bolt://localhost:7687")
    user: str = Field(default="neo4j")
    password: str = Field(default="password")
    database: str = Field(default="neo4j")


class NVDSettings(BaseSettings):
    """NVD API settings."""

    model_config = SettingsConfigDict(env_prefix="NVD_", extra="ignore")

    api_key: str = Field(default="")
    base_url: str = Field(default="https://services.nvd.nist.gov/rest/json/cves/2.0")
    results_per_page: int = Field(default=2000, ge=1, le=2000)
    rate_limit_delay: float = Field(default=6.0, ge=0.0)  # seconds between requests


class TIKGSettings(BaseSettings):
    """Top-level TIKG settings."""

    model_config = SettingsConfigDict(env_prefix="TIKG_", extra="ignore")

    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    nvd: NVDSettings = Field(default_factory=NVDSettings)
    log_level: str = Field(default="INFO")
