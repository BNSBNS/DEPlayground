"""Distribution detector — KS test for numeric column distribution shifts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scipy import stats as scipy_stats

if TYPE_CHECKING:
    import asyncpg

from src.config import get_settings
from src.logging import get_logger
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType

logger = get_logger(__name__)


async def check_distribution(
    pool: asyncpg.Pool[asyncpg.Record],
    table: str,
    column: str,
    reference_values: list[float] | None = None,
) -> DataQualityMetric:
    """Check numeric column distribution using Kolmogorov-Smirnov test.

    Compares current sample distribution against reference distribution.
    KS p-value < 0.01 → critical, < 0.05 → warning.
    """
    settings = get_settings()
    parts = table.split(".")
    db_name = parts[0] if len(parts) > 2 else "default"
    schema_name = parts[1] if len(parts) > 2 else "public"
    table_name = parts[-1]

    warning_p = settings.detectors.distribution_warning_pvalue
    critical_p = settings.detectors.distribution_critical_pvalue

    try:
        # Sample current values (limit to 10k for performance)
        rows = await pool.fetch(
            f"""
            SELECT {column}::DOUBLE PRECISION AS val
            FROM {schema_name}.{table_name}
            WHERE {column} IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 10000
            """
        )
        current_values = [float(row["val"]) for row in rows]
    except Exception as e:
        logger.warning("Distribution check failed", table=table, column=column, error=str(e))
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.DISTRIBUTION,
            value=0.0,
            status=MetricStatus.UNKNOWN,
            metadata={"error": str(e), "column": column},
        )

    if len(current_values) < 30:
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.DISTRIBUTION,
            value=0.0,
            status=MetricStatus.UNKNOWN,
            metadata={"column": column, "note": "insufficient data (<30 rows)"},
        )

    if reference_values is None or len(reference_values) < 30:
        # No reference — store current as baseline, return healthy
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.DISTRIBUTION,
            value=0.0,
            status=MetricStatus.HEALTHY,
            metadata={
                "column": column, "note": "baseline stored", "sample_size": len(current_values),
            },
        )

    # Run KS test
    ks_stat, p_value = scipy_stats.ks_2samp(reference_values, current_values)

    if p_value < critical_p:
        status = MetricStatus.CRITICAL
    elif p_value < warning_p:
        status = MetricStatus.WARNING
    else:
        status = MetricStatus.HEALTHY

    return DataQualityMetric(
        table_name=table_name,
        database=db_name,
        schema_name=schema_name,
        metric_type=MetricType.DISTRIBUTION,
        value=ks_stat,
        status=status,
        metadata={
            "column": column,
            "p_value": p_value,
            "ks_statistic": ks_stat,
            "sample_size": len(current_values),
            "reference_size": len(reference_values),
        },
    )
