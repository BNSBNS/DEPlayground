"""Root Cause Analysis API endpoints."""

import uuid

from fastapi import APIRouter, HTTPException

from src.db.pool import get_pool
from src.logging import get_logger
from src.reasoning.rca import find_root_cause

router = APIRouter()
logger = get_logger(__name__)


@router.post("/rca/{alert_id}")
async def trigger_rca(alert_id: uuid.UUID) -> dict[str, object]:
    """Trigger root cause analysis for an alert."""
    pool = get_pool()

    row = await pool.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    results = await find_root_cause(
        source_table=row["source_table"],
        pool=pool,
    )
    return {
        "alert_id": str(alert_id),
        "source_table": row["source_table"],
        "results": [r.model_dump() for r in results],
    }
