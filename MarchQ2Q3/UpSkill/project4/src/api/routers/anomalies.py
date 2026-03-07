from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_db_pool

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("")
async def get_anomalies(
    severity: str | None = Query(None, description="Filter by severity"),
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    limit: int = Query(100, ge=1, le=1000),
    pool: Any = Depends(get_db_pool),
) -> list[dict[str, Any]]:
    """Get detected anomalies with optional filters."""
    from src.serving.query import query_anomalies

    return await query_anomalies(
        pool, severity=severity, resolved=resolved, limit=limit
    )
