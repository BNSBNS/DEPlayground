import httpx
import structlog

from src.config import get_settings
from src.models.fixes import FixProposal

log = structlog.get_logger(__name__)


async def request_approval(proposal: FixProposal, pr_url: str) -> None:
    """Send an approval request via Slack interactive message (simplified)."""
    settings = get_settings()

    if settings.simulation_mode:
        await log.ainfo(
            "approval_request_simulated",
            proposal_id=str(proposal.proposal_id),
            pr_url=pr_url,
        )
        return

    if not settings.slack_webhook_url:
        await log.awarning("slack_webhook_not_configured_for_approval")
        return

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Approval Required: Auto-Fix PR",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*PR:* {pr_url}\n"
                    f"*Fixes:* {len(proposal.fixes)}\n"
                    f"*Risk:* {', '.join(f.risk_level.value for f in proposal.fixes)}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "value": str(proposal.proposal_id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "value": str(proposal.proposal_id),
                },
            ],
        },
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.slack_webhook_url,
            json={"blocks": blocks},
        )
        if resp.status_code == 200:
            await log.ainfo("approval_request_sent")
        else:
            await log.awarning("approval_request_failed", status=resp.status_code)
