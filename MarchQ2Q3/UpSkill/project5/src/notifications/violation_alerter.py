from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.logging import get_logger
from src.models.contracts import Contract

log = get_logger(__name__)


async def alert_violations(
    contract: Contract, violations: list[dict[str, Any]]
) -> None:
    """Send Slack notification to contract owner with violation details."""
    webhook_url = settings.slack.webhook_url
    if not webhook_url:
        log.warning("slack_webhook_not_configured", contract=contract.name)
        return

    severity_counts: dict[str, int] = {}
    for v in violations:
        sev = v.get("severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    violation_lines = []
    for v in violations[:10]:  # Limit to 10 in notification
        line = f"  - [{v.get('severity', '?').upper()}] {v.get('message', 'No message')}"
        if v.get("field_name"):
            line += f" (field: {v['field_name']})"
        violation_lines.append(line)

    if len(violations) > 10:
        violation_lines.append(f"  ... and {len(violations) - 10} more")

    text = (
        f"*Data Contract Violation Alert*\n"
        f"Contract: *{contract.name}* ({contract.dataset})\n"
        f"Owner: {contract.owner_team} ({contract.owner_contact})\n"
        f"Total violations: {len(violations)}\n"
        f"Severity breakdown: {severity_counts}\n\n"
        f"Details:\n" + "\n".join(violation_lines)
    )

    payload = {"text": text}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        log.info(
            "slack_alert_sent",
            contract=contract.name,
            violations=len(violations),
        )
    except httpx.HTTPError as exc:
        log.error(
            "slack_alert_failed",
            contract=contract.name,
            error=str(exc),
        )
