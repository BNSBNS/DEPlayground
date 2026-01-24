"""Health check endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
    kafka: str


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Check health of all dependencies."""
    db_healthy = request.app.state.db_writer.check_connection()
    kafka_healthy = request.app.state.kafka_streamer.is_connected()

    return HealthResponse(
        status="healthy" if db_healthy and kafka_healthy else "degraded",
        database="connected" if db_healthy else "disconnected",
        kafka="connected" if kafka_healthy else "disconnected",
    )


@router.get("/ready")
async def readiness_check(request: Request) -> dict[str, str]:
    """Kubernetes readiness probe."""
    db_healthy = request.app.state.db_writer.check_connection()
    if not db_healthy:
        return {"status": "not ready", "reason": "database unavailable"}
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe."""
    return {"status": "alive"}
