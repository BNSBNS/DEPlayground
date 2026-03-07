"""Alert routing — severity-based notification dispatch."""

from src.alerting.slack import send_slack_alert
from src.config import get_settings
from src.logging import get_logger
from src.models.alerts import Alert, AlertSeverity

logger = get_logger(__name__)


async def route_alert(alert: Alert) -> None:
    """Route an alert based on severity.

    Critical → Slack + structured log.
    Warning/Info → structured log only.
    """
    logger.info(
        "Alert triggered",
        severity=alert.severity,
        title=alert.title,
        table=alert.source_table,
        metric_type=alert.source_metric_type,
    )

    settings = get_settings()
    if (
        alert.severity == AlertSeverity.CRITICAL
        and settings.alerting.enabled
        and settings.alerting.slack_webhook_url
    ):
        await send_slack_alert(alert, settings.alerting.slack_webhook_url)
