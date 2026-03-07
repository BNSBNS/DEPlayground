"""Webhook receiver endpoints for external integrations.

Supported sources:
  POST /api/v1/webhooks/airflow     — Airflow task failure callbacks
  POST /api/v1/webhooks/openlineage — OpenLineage run events

These are the entry points for *event-driven* observability:
  - Airflow failure → run quality checks on affected tables → route alert
  - OpenLineage COMPLETE → add lineage edges to the in-memory graph
"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.collectors import airflow as airflow_collector
from src.collectors import openlineage as openlineage_collector
from src.db.pool import get_pool
from src.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AirflowCallback(BaseModel):
    """Airflow task failure callback payload."""

    dag_id: str
    task_id: str
    execution_date: str
    try_number: int = 1
    exception: str | None = None


class OpenLineageEvent(BaseModel):
    """OpenLineage run event payload."""

    event_type: str  # START, COMPLETE, FAIL
    run_id: str
    job_name: str
    inputs: list[dict[str, object]] = []
    outputs: list[dict[str, object]] = []


@router.post("/webhooks/airflow")
async def airflow_callback(payload: AirflowCallback) -> dict[str, object]:
    """Receive Airflow task failure callbacks.

    Triggers freshness and volume checks on tables inferred from the task_id,
    then routes alerts for any quality issues found.
    """
    logger.info("airflow_webhook", dag_id=payload.dag_id, task_id=payload.task_id)
    checked = await airflow_collector.handle_failure(
        dag_id=payload.dag_id,
        task_id=payload.task_id,
        pool=get_pool(),
    )
    return {"status": "processed", "dag_id": payload.dag_id, "checked_tables": checked}


@router.post("/webhooks/openlineage")
async def openlineage_event(payload: OpenLineageEvent) -> dict[str, object]:
    """Receive OpenLineage run events and update the lineage graph.

    On COMPLETE events, adds directed edges (input → output) to the in-memory
    graph used by the RCA engine.
    """
    logger.info("openlineage_webhook", event_type=payload.event_type, job=payload.job_name)
    edges = openlineage_collector.handle_event(
        event_type=payload.event_type,
        job_name=payload.job_name,
        inputs=payload.inputs,
        outputs=payload.outputs,
    )
    return {"status": "processed", "event_type": payload.event_type, "edges_added": edges}
