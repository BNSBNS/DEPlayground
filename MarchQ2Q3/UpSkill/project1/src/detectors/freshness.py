"""Freshness detector — checks if a table's data is stale."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import get_settings

if TYPE_CHECKING:
    import asyncpg
from src.logging import get_logger
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType

logger = get_logger(__name__)


async def check_freshness(
    pool: asyncpg.Pool[asyncpg.Record],
    table: str,
    timestamp_column: str = "updated_at",
    max_age_minutes: int | None = None,
) -> DataQualityMetric:
    """Check data freshness by comparing MAX(timestamp_column) to now.

    Args:
        pool: Database connection pool.
        table: Fully qualified table name (database.schema.table).
        timestamp_column: Column to check for latest timestamp.
        max_age_minutes: Override for critical threshold.

    Returns:
        DataQualityMetric with staleness in minutes as the value.
    """
    settings = get_settings()
    parts = table.split(".")
    db_name = parts[0] if len(parts) > 2 else "default"
    schema_name = parts[1] if len(parts) > 2 else "public"
    table_name = parts[-1]

    warning = settings.detectors.freshness_warning_minutes
    critical = max_age_minutes or settings.detectors.freshness_critical_minutes

    try:
        staleness_minutes: float | None = await pool.fetchval(
            f"SELECT EXTRACT(EPOCH FROM (NOW() - MAX({timestamp_column}))) / 60.0 "
            f"FROM {schema_name}.{table_name}"
        )
    except Exception as e:
        logger.warning("Freshness check failed", table=table, error=str(e))
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.FRESHNESS,
            value=0.0,
            status=MetricStatus.UNKNOWN,
            metadata={"error": str(e)},
        )

    if staleness_minutes is None:
        staleness_minutes = 0.0

    status = MetricStatus.HEALTHY
    if staleness_minutes >= critical:
        status = MetricStatus.CRITICAL
    elif staleness_minutes >= warning:
        status = MetricStatus.WARNING

    return DataQualityMetric(
        table_name=table_name,
        database=db_name,
        schema_name=schema_name,
        metric_type=MetricType.FRESHNESS,
        value=staleness_minutes,
        threshold_warning=float(warning),
        threshold_critical=float(critical),
        status=status,
        metadata={"timestamp_column": timestamp_column},
    )
