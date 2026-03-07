"""Metrics API endpoints."""

import json
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.db.pool import get_pool
from src.detectors.freshness import check_freshness
from src.detectors.schema import check_schema
from src.detectors.volume import check_volume
from src.logging import get_logger
from src.models.metrics import DataQualityMetric, MetricType

router = APIRouter()
logger = get_logger(__name__)


class MetricCheckRequest(BaseModel):
    """Request body for triggering a quality check."""

    table_name: str
    database: str
    schema_name: str = "public"
    metric_type: MetricType
    # Detector-specific params
    timestamp_column: str | None = None
    max_age_minutes: int = 60
    min_rows: int | None = None
    max_rows: int | None = None


@router.post("/metrics/check")
async def run_check(request: MetricCheckRequest) -> DataQualityMetric:
    """Run a data quality check and return the metric."""
    pool = get_pool()
    fqn = f"{request.database}.{request.schema_name}.{request.table_name}"

    if request.metric_type == MetricType.FRESHNESS:
        metric = await check_freshness(
            pool,
            table=fqn,
            timestamp_column=request.timestamp_column or "updated_at",
            max_age_minutes=request.max_age_minutes,
        )
    elif request.metric_type == MetricType.VOLUME:
        metric = await check_volume(pool, table=fqn)
    elif request.metric_type == MetricType.SCHEMA:
        metric = await check_schema(pool, table=fqn)
    else:
        metric = DataQualityMetric(
            table_name=request.table_name,
            database=request.database,
            schema_name=request.schema_name,
            metric_type=request.metric_type,
            value=0.0,
        )

    return metric


@router.get("/metrics")
async def list_metrics(
    table_name: str | None = None,
    database: str | None = None,
    metric_type: MetricType | None = None,
    since: datetime | None = None,
    limit: int = Query(default=100, le=1000),
) -> list[dict[str, object]]:
    """Query historical metrics with filters."""
    pool = get_pool()
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    if table_name:
        conditions.append(f"table_name = ${idx}")
        params.append(table_name)
        idx += 1
    if database:
        conditions.append(f"database = ${idx}")
        params.append(database)
        idx += 1
    if metric_type:
        conditions.append(f"metric_type = ${idx}")
        params.append(metric_type.value)
        idx += 1
    if since:
        conditions.append(f"measured_at >= ${idx}")
        params.append(since)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, table_name, database, schema_name, metric_type, value,
               expected_value, threshold_warning, threshold_critical, status,
               metadata, measured_at
        FROM data_quality_metrics
        {where}
        ORDER BY measured_at DESC
        LIMIT ${idx}
    """
    params.append(limit)

    rows = await pool.fetch(query, *params)
    return [
        {
            "id": str(row["id"]),
            "table_name": row["table_name"],
            "database": row["database"],
            "schema_name": row["schema_name"],
            "metric_type": row["metric_type"],
            "value": row["value"],
            "expected_value": row["expected_value"],
            "status": row["status"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "measured_at": row["measured_at"].isoformat(),
        }
        for row in rows
    ]
