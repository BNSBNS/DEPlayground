"""Configuration for InfraScanner."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class InfraScannerSettings(BaseSettings):
    """Application settings loaded from environment variables."""

    osv_base_url: str = "https://api.osv.dev/v1"
    nvd_base_url: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    nvd_api_key: str = ""
    epss_base_url: str = "https://api.first.org/data/v1/epss"

    # Scanning thresholds
    typosquat_max_distance: int = 2
    max_dependencies_per_scan: int = 1000

    # HTTP timeouts
    http_timeout: float = 30.0

    model_config = {"env_prefix": "IS_"}


class APISettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = Field(default=8000)
    api_key: str = Field(default="", description="Optional API key for endpoint auth")

    model_config = {"env_prefix": "IS_API_"}
