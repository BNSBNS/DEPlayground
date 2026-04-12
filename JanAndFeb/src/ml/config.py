"""Configuration for the ML module.

All settings are 12-factor env-overridable with the prefix ``ML_``. For
example ``ML_MODEL_NAME=lightgbm`` at runtime selects the LightGBM strategy.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """Forecasting module settings."""

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        extra="ignore",
    )

    # -------- Core task --------
    model_name: str = Field(
        default="lightgbm",
        description="Default model strategy (sarimax | lightgbm | mlp | gru | cnn).",
    )
    horizon_minutes: int = Field(default=15, ge=1, le=1440)
    seq_len: int = Field(
        default=60,
        ge=8,
        le=1440,
        description="Sliding window length for sequence models (in minutes).",
    )
    symbols: list[str] = Field(default_factory=lambda: ["POWER_DE"])

    # -------- History window --------
    train_history_days: int = Field(default=30, ge=1, le=365)
    infer_history_minutes: int = Field(
        default=240,
        ge=1,
        description="Minutes of history loaded at inference time.",
    )

    # -------- Walk-forward eval --------
    eval_folds: int = Field(default=3, ge=1, le=10)
    min_train_rows: int = Field(default=500, ge=100)

    # -------- Storage & scheduling --------
    model_store_path: Path = Field(default=Path("data/ml_models"))
    retrain_cron: str = Field(
        default="0 2 * * *",
        description="APScheduler cron expression for periodic retraining.",
    )
    metrics_port: int = Field(default=8004, ge=1, le=65535)

    # -------- Neural hparams --------
    hidden_size: int = Field(default=64, ge=4)
    num_layers: int = Field(default=2, ge=1)
    dropout: float = Field(default=0.1, ge=0.0, lt=1.0)
    batch_size: int = Field(default=64, ge=1)
    epochs: int = Field(default=50, ge=1)
    learning_rate: float = Field(default=1e-3, gt=0.0)
    early_stopping_patience: int = Field(default=5, ge=1)


@lru_cache(maxsize=1)
def get_ml_settings() -> MLSettings:
    """Cached singleton accessor — matches the pattern used in ``src.common.config``."""
    return MLSettings()
