from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    dsn: str = "postgresql://contracts:contracts@localhost:5435/data_contracts"


class SlackSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SLACK_")

    webhook_url: str = ""


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_")

    port: int = 8050


class EnforcementSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENFORCEMENT_")

    check_interval_seconds: int = 60


class GovernanceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOVERNANCE_")

    audit_enabled: bool = True


class Settings(BaseSettings):
    postgres: PostgresSettings = PostgresSettings()
    slack: SlackSettings = SlackSettings()
    api: APISettings = APISettings()
    enforcement: EnforcementSettings = EnforcementSettings()
    governance: GovernanceSettings = GovernanceSettings()


settings = Settings()
