"""Airflow event collector — triggers quality checks when a pipeline task fails.

Called from the webhook endpoint at POST /api/v1/webhooks/airflow.

Learning note:
  This is the entry point for *event-driven* observability: rather than polling
  tables on a schedule, we react immediately when Airflow reports a failure.
  The quality check runs on affected tables and routes an alert if needed.
"""

from __future__ import annotations

import asyncpg

from src.alerting.router import route_alert
from src.db.pool import save_metric
from src.detectors.freshness import check_freshness
from src.logging import get_logger
from src.models.alerts import Alert, AlertSeverity, AlertState
from src.models.metrics import MetricStatus

logger = get_logger(__name__)


def infer_tables_from_task(dag_id: str, task_id: str) -> list[str]:
    """Extract probable table name from Airflow task_id by convention.

    Convention: load_orders → orders, transform_sales → sales,
    anything_else → task_id as-is (best effort).
    """
    prefixes = ("load_", "transform_", "extract_", "ingest_", "sync_", "refresh_")
    for prefix in prefixes:
        if task_id.startswith(prefix):
            return [task_id[len(prefix):]]
    return [task_id]


async def handle_failure(
    dag_id: str,
    task_id: str,
    pool: asyncpg.Pool,
    *,
    affected_tables: list[str] | None = None,
) -> list[str]:
    """Run freshness checks on tables affected by an Airflow task failure.

    Args:
        dag_id: The Airflow DAG that failed.
        task_id: The specific task that failed.
        pool: DB connection pool.
        affected_tables: Optional explicit list; inferred from task_id if not given.

    Returns:
        List of table names that were checked.
    """
    tables = affected_tables or infer_tables_from_task(dag_id, task_id)
    logger.info("airflow_failure_handling", dag_id=dag_id, task_id=task_id, tables=tables)

    for table in tables:
        metric = await check_freshness(pool, table=table, timestamp_column="updated_at")
        await save_metric(pool, metric)

        logger.info(
            "table_checked_after_failure",
            table=table,
            status=metric.status.value,
            stale_minutes=metric.value,
        )

        if metric.status in (MetricStatus.WARNING, MetricStatus.CRITICAL):
            severity = (
                AlertSeverity.CRITICAL
                if metric.status == MetricStatus.CRITICAL
                else AlertSeverity.WARNING
            )
            alert = Alert(
                title=f"Pipeline failure impact: {table} {metric.status.value.upper()}",
                description=(
                    f"Airflow DAG '{dag_id}' task '{task_id}' failed. "
                    f"Table '{table}' is now {metric.value:.1f} minutes stale."
                ),
                severity=severity,
                state=AlertState.OPEN,
                source_table=table,
                source_metric_type="freshness",
            )
            await route_alert(alert)

    return tables
