"""REST endpoints for the forecasting module.

Mounted into the main FastAPI app at ``/api/v1``. All endpoints are
read-only: they query the ``forecasts``, ``anomaly_scores``, and
``model_registry`` tables that the separate ``ml-scheduler`` /
``ml-trainer`` containers populate. The API container is intentionally
lean and does NOT carry torch / lightgbm / statsmodels — fresh inference
lives in the ML worker containers, not here.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal  # noqa: TC003  (used as Pydantic field type at class-body time)
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.ml.domain.models import Forecast

router = APIRouter()


# --------------------------------------------------------------------------
# Response schemas
# --------------------------------------------------------------------------
class ForecastResponse(BaseModel):
    """Single forecast row returned by the API."""

    symbol: str
    forecast_for: datetime
    generated_at: datetime
    horizon_minutes: int
    yhat: Decimal = Field(decimal_places=8)
    yhat_lower: Decimal | None = Field(default=None, decimal_places=8)
    yhat_upper: Decimal | None = Field(default=None, decimal_places=8)
    model_name: str
    model_version: str
    feature_hash: str


class ForecastBatchResponse(BaseModel):
    symbol: str
    model_name: str
    model_version: str
    forecasts: list[ForecastResponse]


class AnomalyResponse(BaseModel):
    symbol: str
    window_start: datetime
    score: float
    is_anomaly: bool
    detector_name: str


class ModelSummary(BaseModel):
    model_name: str
    model_version: str
    trained_at: datetime
    metrics: dict[str, float]
    artifact_uri: str


# --------------------------------------------------------------------------
# Forecasts
# --------------------------------------------------------------------------
@router.get("/forecasts/{symbol}", response_model=ForecastBatchResponse)
async def get_latest_forecast(
    request: Request,
    symbol: str,
    model: Annotated[str, Query(description="Model name")] = "lightgbm",
    horizon: Annotated[int, Query(ge=1, le=1440)] = 15,
) -> ForecastBatchResponse:
    """Return the most recent forecast batch for ``symbol``.

    Reads from the ``forecasts`` hypertable. Fresh inference is performed
    out-of-band by the ``ml-scheduler`` container, which writes its
    results back to the same hypertable — so this endpoint stays a pure
    read path.
    """
    # ``horizon`` doubles as the row-limit: a recursive forecaster emits one
    # row per minute-ahead step, so asking for the latest `horizon` rows of
    # a given (symbol, model) gives you a single horizon-length batch.
    batch = await asyncio.to_thread(
        _forecast_repo(request).load_latest,
        symbol,
        model,
        horizon,
    )

    if not batch.forecasts:
        raise HTTPException(
            status_code=404,
            detail=f"No forecast available for symbol={symbol} model={model}",
        )

    first = batch.forecasts[0]
    return ForecastBatchResponse(
        symbol=symbol,
        model_name=first.model_name,
        model_version=first.model_version,
        forecasts=[_forecast_to_response(f) for f in batch.forecasts],
    )


@router.get("/anomalies/{symbol}", response_model=list[AnomalyResponse])
async def get_anomalies(
    request: Request,
    symbol: str,
    hours: Annotated[int, Query(ge=1, le=720)] = 24,
    only_flagged: Annotated[bool, Query()] = True,
) -> list[AnomalyResponse]:
    """Return anomaly scores for ``symbol`` within the last ``hours``."""
    db = request.app.state.db_writer
    since = datetime.now(UTC) - timedelta(hours=hours)

    sql = """
        SELECT symbol, window_start, score, is_anomaly, detector_name
        FROM anomaly_scores
        WHERE symbol = %(symbol)s AND window_start >= %(since)s
    """
    params: dict[str, Any] = {"symbol": symbol, "since": since}
    if only_flagged:
        sql += " AND is_anomaly = true"
    sql += " ORDER BY window_start DESC LIMIT 1000"

    rows = await asyncio.to_thread(db.query_all, sql, params)
    return [AnomalyResponse(**row) for row in rows]


@router.get("/models", response_model=list[ModelSummary])
async def list_models(request: Request) -> list[ModelSummary]:
    """List all trained model versions (lineage from ``model_registry``)."""
    registry_repo = request.app.state.ml_registry_repo
    metas = await asyncio.to_thread(registry_repo.list_all)
    return [
        ModelSummary(
            model_name=m.model_name,
            model_version=m.model_version,
            trained_at=m.trained_at,
            metrics=m.metrics,
            artifact_uri=m.artifact_uri,
        )
        for m in metas
    ]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _forecast_repo(request: Request) -> Any:
    repo = getattr(request.app.state, "ml_forecast_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Forecast repository not wired.")
    return repo


def _forecast_to_response(f: Forecast) -> ForecastResponse:
    return ForecastResponse(
        symbol=f.symbol,
        forecast_for=f.forecast_for,
        generated_at=f.generated_at,
        horizon_minutes=f.horizon_minutes,
        yhat=f.yhat,
        yhat_lower=f.yhat_lower,
        yhat_upper=f.yhat_upper,
        model_name=f.model_name,
        model_version=f.model_version,
        feature_hash=f.feature_hash,
    )
