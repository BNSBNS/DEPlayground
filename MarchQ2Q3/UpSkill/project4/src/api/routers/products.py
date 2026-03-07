from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_db_pool

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/performance")
async def get_product_performance(
    product_id: str | None = Query(None, description="Filter by product ID"),
    start: datetime | None = Query(None, description="Window start (ISO 8601)"),
    end: datetime | None = Query(None, description="Window end (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000),
    pool: Any = Depends(get_db_pool),
) -> list[dict[str, Any]]:
    """Get product performance metrics with optional filters."""
    from src.serving.query import query_product_performance

    return await query_product_performance(
        pool, product_id=product_id, start=start, end=end, limit=limit
    )
