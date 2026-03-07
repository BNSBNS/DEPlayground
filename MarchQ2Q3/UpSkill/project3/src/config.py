from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration via environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Postgres
    postgres_dsn: str = "postgresql://agent:agent@localhost:5433/data_agent"

    # LLM
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: str = ""

    # GitHub
    github_token: str = ""
    github_owner: str = ""
    github_repo: str = ""

    # Slack
    slack_webhook_url: str = ""

    # Agent
    agent_max_iterations: int = 3
    agent_rate_limit_per_hour: int = 10
    approval_timeout_seconds: int = 300
    simulation_mode: bool = True

    # API
    api_port: int = 8030


def get_settings() -> Settings:
    return Settings()
