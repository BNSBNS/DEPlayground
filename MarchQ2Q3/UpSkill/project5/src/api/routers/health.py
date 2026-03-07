from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.db.pool import get_pool
from src.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, Any]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        log.error("readiness_check_failed", error=str(exc))
        return {"status": "not_ready", "database": str(exc)}


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}
