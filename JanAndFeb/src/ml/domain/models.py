"""Domain models for the forecasting layer.

These are pure Pydantic v2 models — no ML libraries, no I/O.
They mirror the precision conventions of `src.common.models`
(NUMERIC(18,8) for prices) to keep the trading and forecasting layers
type-compatible on the wire and in the database.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Forecast(BaseModel):
    """A single forecasted value for a symbol at a target timestamp.

    A forecast is always tagged with the model name and version that produced
    it, plus a ``feature_hash`` that captures exactly which feature set was
    used. This is the minimum viable lineage for reproducibility and A/B
    comparison in the ``model_registry`` and ``forecasts`` tables.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        frozen=True,
    )

    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9_]+$")
    forecast_for: datetime
    generated_at: datetime
    horizon_minutes: int = Field(gt=0, le=1440)
    yhat: Decimal = Field(decimal_places=8)
    yhat_lower: Decimal | None = Field(default=None, decimal_places=8)
    yhat_upper: Decimal | None = Field(default=None, decimal_places=8)
    model_name: str = Field(min_length=1, max_length=64)
    model_version: str = Field(min_length=1, max_length=64)
    feature_hash: str = Field(min_length=1, max_length=128)

    @field_validator("yhat", "yhat_lower", "yhat_upper", mode="before")
    @classmethod
    def _to_decimal(cls, v: float | int | str | Decimal | None) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("forecast_for", "generated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str) -> datetime:
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class ForecastBatch(BaseModel):
    """A collection of forecasts produced by a single inference call."""

    model_config = ConfigDict(frozen=True)

    forecasts: list[Forecast]

    def __len__(self) -> int:
        return len(self.forecasts)

    def __iter__(self) -> Iterator[Forecast]:  # type: ignore[override]
        return iter(self.forecasts)


class AnomalyScore(BaseModel):
    """Anomaly signal for a single (symbol, window) emitted by a detector."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        frozen=True,
    )

    symbol: str = Field(min_length=1, max_length=20)
    window_start: datetime
    score: float
    is_anomaly: bool
    detector_name: str = Field(min_length=1, max_length=64)

    @field_validator("window_start", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str) -> datetime:
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class ModelMetadata(BaseModel):
    """Lineage for a trained model — what was fit, how well, and where it lives.

    Written to the ``model_registry`` table after every successful training run.
    The ``artifact_uri`` points into a ``ModelStore`` implementation
    (filesystem by default).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        frozen=True,
    )

    model_name: str = Field(min_length=1, max_length=64)
    model_version: str = Field(min_length=1, max_length=64)
    trained_at: datetime
    metrics: dict[str, float]
    params: dict[str, Any]
    artifact_uri: str = Field(min_length=1)

    @field_validator("trained_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str) -> datetime:
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v
