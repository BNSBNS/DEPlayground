"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> HealthResponse:
    """Liveness probe — always returns 200 if the process is running."""
    return HealthResponse(status="ok")


@router.get("/health/ready")
def readiness() -> HealthResponse:
    """Readiness probe — returns 200 when the app is ready to serve."""
    return HealthResponse(status="ready")
