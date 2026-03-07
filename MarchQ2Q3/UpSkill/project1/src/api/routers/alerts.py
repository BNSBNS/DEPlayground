"""Alert API endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Query

from src.db.pool import get_pool
from src.logging import get_logger
from src.models.alerts import AlertSeverity, AlertState

router = APIRouter()
logger = get_logger(__name__)


@router.get("/alerts")
async def list_alerts(
    state: AlertState | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(default=50, le=500),
) -> list[dict[str, object]]:
    """List alerts with optional filters."""
    pool = get_pool()
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    if state:
        conditions.append(f"state = ${idx}")
        params.append(state.value)
        idx += 1
    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity.value)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, title, description, severity, state, source_table,
               source_metric_type, root_cause, suggested_remediation,
               created_at, acknowledged_at, resolved_at
        FROM alerts
        {where}
        ORDER BY created_at DESC
        LIMIT ${idx}
    """
    params.append(limit)

    rows = await pool.fetch(query, *params)
    return [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "severity": row["severity"],
            "state": row["state"],
            "source_table": row["source_table"],
            "source_metric_type": row["source_metric_type"],
            "root_cause": row["root_cause"],
            "suggested_remediation": row["suggested_remediation"],
            "created_at": row["created_at"].isoformat(),
            "acknowledged_at": (
                row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None
            ),
            "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
        }
        for row in rows
    ]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: uuid.UUID) -> dict[str, str]:
    """Acknowledge an open alert."""
    pool = get_pool()
    result = await pool.execute(
        """
        UPDATE alerts SET state = 'acknowledged', acknowledged_at = NOW()
        WHERE id = $1 AND state = 'open'
        """,
        alert_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Alert not found or not in 'open' state")
    return {"status": "acknowledged", "alert_id": str(alert_id)}
