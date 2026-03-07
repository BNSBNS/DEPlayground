from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException

from src.models.events import PipelineFailureEvent

log = structlog.get_logger(__name__)
router = APIRouter(tags=["events"])

# In-memory store for simulation mode
_runs: dict[str, dict] = {}


@router.post("/events")
async def receive_event(event: PipelineFailureEvent) -> dict[str, str]:
    """Receive a pipeline failure event and trigger the agent."""
    run_id = str(uuid.uuid4())
    _runs[run_id] = {
        "run_id": run_id,
        "event_id": str(event.event_id),
        "pipeline": event.pipeline_name,
        "task": event.task_name,
        "status": "received",
        "error_type": event.error_type,
    }

    await log.ainfo("event_received", run_id=run_id, event_id=str(event.event_id))

    # In production, this would invoke the agent graph asynchronously.
    # For now, we store and return the run_id.
    return {"run_id": run_id, "status": "received"}


@router.get("/runs")
async def list_runs() -> list[dict]:
    """List all agent runs."""
    return list(_runs.values())


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    """Get details of a specific agent run."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run
