"""Volume detector — checks row count against historical baseline using z-score."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.config import get_settings

if TYPE_CHECKING:
    import asyncpg
from src.logging import get_logger
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType

logger = get_logger(__name__)


def compute_zscore(value: float, values: list[float]) -> float | None:
    """Compute z-score of value relative to a list of historical values."""
    if len(values) < 3:
        return None
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (value - mean) / std


async def check_volume(
    pool: asyncpg.Pool[asyncpg.Record],
    table: str,
) -> DataQualityMetric:
    """Check table row count against historical baseline.

    Compares current COUNT(*) to a rolling window of historical counts using
    z-score. Requires 3+ historical data points; returns unknown otherwise.
    """
    settings = get_settings()
    parts = table.split(".")
    db_name = parts[0] if len(parts) > 2 else "default"
    schema_name = parts[1] if len(parts) > 2 else "public"
    table_name = parts[-1]

    warning_z = settings.detectors.volume_warning_zscore
    critical_z = settings.detectors.volume_critical_zscore
    lookback = settings.detectors.volume_lookback_days

    try:
        current_count: int = await pool.fetchval(
            f"SELECT COUNT(*) FROM {schema_name}.{table_name}"
        )
    except Exception as e:
        logger.warning("Volume check failed", table=table, error=str(e))
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.VOLUME,
            value=0.0,
            status=MetricStatus.UNKNOWN,
            metadata={"error": str(e)},
        )

    # Fetch historical volume metrics
    history = await pool.fetch(
        """
        SELECT value FROM data_quality_metrics
        WHERE table_name = $1 AND database = $2 AND metric_type = 'volume'
        AND measured_at > NOW() - INTERVAL '1 day' * $3
        ORDER BY measured_at DESC
        """,
        table_name,
        db_name,
        lookback,
    )
    historical_values = [float(row["value"]) for row in history]

    zscore = compute_zscore(float(current_count), historical_values)

    if zscore is None:
        status = MetricStatus.UNKNOWN
    elif abs(zscore) >= critical_z:
        status = MetricStatus.CRITICAL
    elif abs(zscore) >= warning_z:
        status = MetricStatus.WARNING
    else:
        status = MetricStatus.HEALTHY

    return DataQualityMetric(
        table_name=table_name,
        database=db_name,
        schema_name=schema_name,
        metric_type=MetricType.VOLUME,
        value=float(current_count),
        threshold_warning=warning_z,
        threshold_critical=critical_z,
        status=status,
        metadata={
            "zscore": zscore,
            "historical_count": len(historical_values),
            "lookback_days": lookback,
        },
    )
