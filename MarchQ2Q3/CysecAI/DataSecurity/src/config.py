"""DataSecurity application settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DataSecuritySettings(BaseSettings):
    """Configurable settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="DS_", env_file=".env", extra="ignore")

    # Database URLs (no defaults — must be provided in environment)
    postgres_url: str = ""
    mysql_url: str = ""

    # API security
    api_key: str = "dev-key-change-in-production"

    # PII detection config
    pii_config_path: str = "config/pii_patterns.yaml"

    # Thresholds
    bulk_select_threshold: int = 10_000
    max_sample_rows: int = 100

    # Off-hours detection (24-hour format)
    off_hours_start: int = 22  # 10 PM
    off_hours_end: int = 6  # 6 AM
    business_timezone: str = "Asia/Singapore"
