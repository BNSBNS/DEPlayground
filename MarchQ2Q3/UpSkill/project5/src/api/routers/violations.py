from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query

from src.db.pool import get_pool
from src.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/violations", tags=["violations"])


@router.get("")
async def list_violations(
    dataset: str | None = Query(None),
    violation_type: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    pool = await get_pool()

    query = "SELECT * FROM violations WHERE 1=1"
    params: list[object] = []
    idx = 1

    if dataset is not None:
        query += f" AND dataset = ${idx}"
        params.append(dataset)
        idx += 1

    if violation_type is not None:
        query += f" AND violation_type = ${idx}"
        params.append(violation_type)
        idx += 1

    if severity is not None:
        query += f" AND severity = ${idx}"
        params.append(severity)
        idx += 1

    query += f" ORDER BY detected_at DESC LIMIT ${idx}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    results = []
    for r in rows:
        row_dict = dict(r)
        # Convert UUID/datetime to string for JSON serialization
        for k, v in row_dict.items():
            if hasattr(v, "hex"):  # UUID
                row_dict[k] = str(v)
            elif hasattr(v, "isoformat"):  # datetime
                row_dict[k] = v.isoformat()
        results.append(row_dict)

    return results
