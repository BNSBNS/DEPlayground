"""TIKG FastAPI application — query the threat intelligence knowledge graph."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.query_engine.nl_to_cypher import NLQueryEngine, QueryResult

# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------


class _AppState:
    engine: NLQueryEngine = NLQueryEngine()


_state = _AppState()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="TIKG API",
    description="Threat Intelligence Knowledge Graph — query CVEs, techniques, KEV, and more.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class NLQueryRequest(BaseModel):
    question: str


class NLQueryResponse(BaseModel):
    question: str
    intent: str
    cypher: str
    parameters: dict[str, Any]
    confidence: float


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/api/v1/query", response_model=NLQueryResponse)
async def nl_query(request: NLQueryRequest) -> NLQueryResponse:
    """Translate a natural language question to Cypher."""
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty")
    result: QueryResult = _state.engine.translate(request.question)
    return NLQueryResponse(
        question=result.natural_language,
        intent=result.intent,
        cypher=result.cypher,
        parameters=result.parameters,
        confidence=result.confidence,
    )


@app.get("/api/v1/intents")
async def list_intents() -> dict[str, list[str]]:
    """List supported query intents."""
    return {
        "intents": [
            "cve_by_id",
            "top_cves",
            "critical_cves",
            "high_cves",
            "kev_status",
            "cves_for_vendor",
            "techniques_by_tactic",
            "techniques_for_cve",
            "epss_high",
            "unknown",
        ]
    }
