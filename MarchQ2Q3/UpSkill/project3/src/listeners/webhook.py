import structlog
from fastapi import APIRouter

from src.models.events import PipelineFailureEvent

log = structlog.get_logger(__name__)
router = APIRouter(tags=["webhook"])


@router.post("/webhook/failure")
async def receive_failure(event: PipelineFailureEvent) -> dict[str, str]:
    """Receive a pipeline failure event from an orchestrator webhook."""
    await log.ainfo(
        "webhook_received",
        event_id=str(event.event_id),
        pipeline=event.pipeline_name,
        task=event.task_name,
    )
    # In a real system, this would trigger the agent graph.
    # For now, we return the event_id for tracking.
    return {"status": "received", "event_id": str(event.event_id)}
