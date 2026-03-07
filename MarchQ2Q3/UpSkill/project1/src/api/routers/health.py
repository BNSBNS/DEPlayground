"""Health check endpoints."""

from fastapi import APIRouter

from src.db.pool import get_pool
from src.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, object]:
    """Deep health check — verifies database connectivity."""
    checks: dict[str, str] = {}
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if healthy else "degraded", "checks": checks}
