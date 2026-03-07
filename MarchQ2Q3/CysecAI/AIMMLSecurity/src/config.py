"""Project configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class FirewallSettings(BaseSettings):
    """AI/LLM security firewall settings."""

    model_config = {"env_prefix": "AIML_"}

    block_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_prompt_length: int = Field(default=10000, ge=100)
    dataset_path: Path = Path(__file__).resolve().parents[1] / "attack_samples" / "dataset.json"
    model_dir: Path = Path(__file__).resolve().parents[1] / "models"
