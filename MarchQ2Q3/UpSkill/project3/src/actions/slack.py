import httpx
import structlog

from src.config import get_settings
from src.models.state import AgentState

log = structlog.get_logger(__name__)


async def send_notification(state: AgentState) -> None:
    """Send a Slack notification with diagnosis and PR link."""
    settings = get_settings()

    if settings.simulation_mode:
        await log.ainfo("slack_notification_simulated", pr_url=state.get("pr_url", ""))
        return

    if not settings.slack_webhook_url:
        await log.awarning("slack_webhook_not_configured")
        return

    event = state["event"]
    diagnosis = state.get("diagnosis")
    pr_url = state.get("pr_url", "N/A")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Pipeline Fix: {event.pipeline_name}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Task:* {event.task_name}"},
                {"type": "mrkdwn", "text": f"*Error:* {event.error_type}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Diagnosis:* {diagnosis.category if diagnosis else 'N/A'}",
                },
                {"type": "mrkdwn", "text": f"*PR:* {pr_url}"},
            ],
        },
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.slack_webhook_url,
            json={"blocks": blocks},
        )
        if resp.status_code == 200:
            await log.ainfo("slack_notification_sent")
        else:
            await log.awarning("slack_notification_failed", status=resp.status_code)
