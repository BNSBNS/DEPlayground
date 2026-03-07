"""FastAPI fraud scoring API.

Endpoints: POST /score, POST /batch, GET /model-info, GET /stats, GET /health.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import numpy as np
from fastapi import FastAPI

from src.api.schemas import (
    BatchScoringRequest,
    BatchScoringResponse,
    FeatureContribution,
    ModelInfo,
    ScoringRequest,
    ScoringResponse,
    StatsResponse,
)
from src.features.pipeline import FEATURE_COLUMNS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from src.models.base import BaseDetector


class _AppState:
    """Mutable app state for model and statistics."""

    def __init__(self) -> None:
        self.model: BaseDetector | None = None
        self.model_name: str = "ensemble"
        self.model_type: str = "WeightedEnsemble"
        self.total_scored: int = 0
        self.total_flagged: int = 0
        self.score_sum: float = 0.0


state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """Startup/shutdown lifecycle. Model must be set before startup."""
    yield


app = FastAPI(
    title="Fraud Detection API",
    version="1.0.0",
    description="Real-time fraud scoring for financial transactions",
    lifespan=lifespan,
)


def set_model(model: BaseDetector, name: str = "ensemble", model_type: str = "Ensemble") -> None:
    """Inject a trained model into the API (call before starting the server)."""
    state.model = model
    state.model_name = name
    state.model_type = model_type


def _score_single(req: ScoringRequest) -> ScoringResponse:
    """Score a single transaction."""
    assert state.model is not None, "Model not loaded"

    features = np.array([[req.features.get(f, 0.0) for f in FEATURE_COLUMNS]])
    score = float(state.model.score(features)[0])
    preds = state.model.predict(features)
    is_fraud = bool(preds[0] == 1)
    explanations = state.model.explain(features, list(FEATURE_COLUMNS))

    state.total_scored += 1
    state.score_sum += score
    if is_fraud:
        state.total_flagged += 1

    return ScoringResponse(
        transaction_id=req.transaction_id,
        fraud_score=round(score, 4),
        is_fraud=is_fraud,
        explanation=[
            FeatureContribution(feature=name, contribution=round(val, 4))
            for name, val in explanations[0]
        ],
    )


@app.post("/api/v1/score", response_model=ScoringResponse)
async def score_transaction(req: ScoringRequest) -> ScoringResponse:
    """Score a single transaction for fraud."""
    return _score_single(req)


@app.post("/api/v1/batch", response_model=BatchScoringResponse)
async def score_batch(req: BatchScoringRequest) -> BatchScoringResponse:
    """Score a batch of transactions."""
    results = [_score_single(tx) for tx in req.transactions]
    flagged = sum(1 for r in results if r.is_fraud)
    return BatchScoringResponse(
        results=results,
        total=len(results),
        flagged=flagged,
    )


@app.get("/api/v1/model-info", response_model=ModelInfo)
async def model_info() -> ModelInfo:
    """Get model metadata."""
    return ModelInfo(
        model_name=state.model_name,
        model_type=state.model_type,
        feature_count=len(FEATURE_COLUMNS),
        feature_names=list(FEATURE_COLUMNS),
    )


@app.get("/api/v1/stats", response_model=StatsResponse)
async def stats() -> StatsResponse:
    """Get API usage statistics."""
    avg = state.score_sum / state.total_scored if state.total_scored > 0 else 0.0
    rate = state.total_flagged / state.total_scored if state.total_scored > 0 else 0.0
    return StatsResponse(
        total_scored=state.total_scored,
        total_flagged=state.total_flagged,
        flagged_rate=round(rate, 4),
        avg_score=round(avg, 4),
    )


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check."""
    return {"status": "ok", "model_loaded": state.model is not None}
