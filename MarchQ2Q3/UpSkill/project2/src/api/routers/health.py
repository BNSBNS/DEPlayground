"""Health check endpoints."""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter

from src.db.pool import get_pool

router = APIRouter(tags=["health"])


async def _check_db() -> dict[str, Any]:
    """Verify database connectivity."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok"}
    except (RuntimeError, asyncpg.PostgresError) as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health")
async def health() -> dict[str, Any]:
    """Deep health check — verifies database connectivity."""
    db = await _check_db()
    overall = "ok" if db["status"] == "ok" else "degraded"
    return {"status": overall, "checks": {"database": db}}


@router.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness probe — returns ok when the service can accept traffic."""
    return {"status": "ok"}


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness probe — returns ok if the process is alive."""
    return {"status": "ok"}
