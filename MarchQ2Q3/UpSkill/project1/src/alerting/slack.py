"""Slack notification sender."""

import httpx

from src.logging import get_logger
from src.models.alerts import Alert

logger = get_logger(__name__)


async def send_slack_alert(alert: Alert, webhook_url: str) -> bool:
    """Send an alert notification to Slack via webhook.

    Returns True if sent successfully, False otherwise.
    """
    payload = {
        "text": f":warning: *{alert.severity.upper()}* — {alert.title}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{alert.title}*\n"
                        f"Severity: `{alert.severity}`\n"
                        f"Table: `{alert.source_table}`\n"
                        f"Type: `{alert.source_metric_type}`\n"
                        f"{alert.description}"
                    ),
                },
            }
        ],
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
        logger.info("Slack alert sent", alert_id=str(alert.id), title=alert.title)
        return True
    except Exception as e:
        logger.error("Failed to send Slack alert", error=str(e), alert_id=str(alert.id))
        return False
