import httpx
import structlog

from src.config import get_settings
from src.models.state import AgentState

log = structlog.get_logger(__name__)


async def send_escalation(state: AgentState) -> None:
    """Send escalation message for unresolvable failures."""
    settings = get_settings()
    event = state["event"]
    error = state.get("error", "Max iterations exceeded without valid fix")
    validation_errors = state.get("validation_errors", [])

    if settings.simulation_mode:
        await log.awarning(
            "escalation_simulated",
            pipeline=event.pipeline_name,
            task=event.task_name,
            error=error,
            validation_errors=validation_errors,
        )
        return

    if not settings.slack_webhook_url:
        await log.awarning("slack_webhook_not_configured_for_escalation")
        return

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "ESCALATION: Pipeline Fix Failed",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Pipeline:* {event.pipeline_name}\n"
                    f"*Task:* {event.task_name}\n"
                    f"*Error:* {event.error_message}\n"
                    f"*Reason:* {error}\n"
                    f"*Validation Errors:* {'; '.join(validation_errors)}"
                ),
            },
        },
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.slack_webhook_url,
            json={"blocks": blocks},
        )
        if resp.status_code == 200:
            await log.ainfo("escalation_sent")
        else:
            await log.awarning("escalation_failed", status=resp.status_code)
