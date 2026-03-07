from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "streaming-analytics",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness probe -- checks downstream dependencies."""
    # In production, check Redis/Kafka/Postgres connectivity
    return {"status": "ready"}
