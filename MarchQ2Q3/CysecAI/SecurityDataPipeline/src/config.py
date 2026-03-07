"""Configuration for Security Data Pipeline.

Extends BaseProjectSettings from cysec-shared. GeneratorSettings controls
synthetic log generation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from cysec_shared.config import BaseProjectSettings


class GeneratorSettings(BaseModel):
    """Settings for synthetic log generation."""

    num_events: int = Field(default=10000, ge=100)
    attack_rate: float = Field(default=0.05, ge=0.01, le=0.30)
    num_users: int = Field(default=50, ge=5)
    num_hosts: int = Field(default=20, ge=3)
    seed: int = Field(default=42)

    @field_validator("attack_rate")
    @classmethod
    def validate_attack_rate(cls, v: float) -> float:
        """Ensure attack rate is within reasonable bounds."""
        if not 0.01 <= v <= 0.30:
            msg = "attack_rate must be between 0.01 and 0.30"
            raise ValueError(msg)
        return v


class SIEMSettings(BaseProjectSettings):
    """Project-level settings for the SIEM pipeline."""

    generator: GeneratorSettings = Field(default_factory=GeneratorSettings)
    sigma_rules_dir: str = Field(default="rules")
    correlation_window_seconds: int = Field(default=600, ge=60)
    max_events_per_batch: int = Field(default=1000, ge=10)
