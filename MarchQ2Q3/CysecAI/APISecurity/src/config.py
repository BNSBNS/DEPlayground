"""Configuration settings for APISecurity scanner and vulnerable test app."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class ScannerSettings(BaseSettings):
    """Settings for the API security scanner."""

    target_url: str = "http://localhost:8001"
    request_timeout: float = 10.0
    max_concurrent: int = 5
    destructive: bool = False  # require --destructive flag for state-changing tests

    model_config = {"env_prefix": "SCANNER_"}


class VulnerableAppSettings(BaseSettings):
    """Settings for the deliberately vulnerable test API."""

    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = True  # intentionally verbose

    model_config = {"env_prefix": "VULN_APP_"}
