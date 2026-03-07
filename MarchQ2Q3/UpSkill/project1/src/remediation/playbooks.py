"""Remediation playbooks — condition-to-action mappings."""

from src.logging import get_logger
from src.models.metrics import MetricType
from src.models.remediation import RemediationLog, RemediationResult

logger = get_logger(__name__)


async def remediate_freshness(
    table: str, dry_run: bool = True
) -> RemediationLog:
    """Remediation for stale data: trigger pipeline rerun."""
    if dry_run:
        logger.info("DRY RUN: would trigger refresh", table=table)
        return RemediationLog(
            alert_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            action_type="trigger_refresh",
            action_detail={"table": table, "dry_run": True},
            result=RemediationResult.SKIPPED,
        )
    # Actual execution would call Airflow API here
    logger.info("Triggering data refresh", table=table)
    return RemediationLog(
        alert_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
        action_type="trigger_refresh",
        action_detail={"table": table},
        result=RemediationResult.SUCCESS,
    )


# Map metric types to remediation functions
PLAYBOOKS = {
    MetricType.FRESHNESS: remediate_freshness,
}
