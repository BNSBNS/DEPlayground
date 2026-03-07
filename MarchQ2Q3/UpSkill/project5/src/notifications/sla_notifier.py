from __future__ import annotations

import httpx

from src.config import settings
from src.logging import get_logger
from src.models.contracts import Contract
from src.models.sla import SLARecord
from src.models.versions import ContractVersion

log = get_logger(__name__)


async def notify_sla_breach(
    contract: Contract,
    version: ContractVersion,
    sla_record: SLARecord,
) -> None:
    """Notify contract owner and consumers on SLA miss."""
    webhook_url = settings.slack.webhook_url
    if not webhook_url:
        log.warning("slack_webhook_not_configured", contract=contract.name)
        return

    consumer_list = ", ".join(version.consumers) if version.consumers else "none"

    text = (
        f"*SLA Breach Alert*\n"
        f"Contract: *{contract.name}* ({contract.dataset})\n"
        f"Owner: {contract.owner_team} ({contract.owner_contact})\n"
        f"Consumers: {consumer_list}\n\n"
        f"Period: {sla_record.period_start:%Y-%m-%d %H:%M} - "
        f"{sla_record.period_end:%Y-%m-%d %H:%M}\n"
        f"Expected updates: {sla_record.expected_updates}\n"
        f"Actual updates: {sla_record.actual_updates}\n"
        f"Missed updates: {sla_record.missed_updates}\n"
        f"Max observed latency: {sla_record.max_observed_latency:.0f}s\n"
        f"Availability: {sla_record.availability_pct:.1f}%\n"
        f"Compliant: {sla_record.compliant}"
    )

    payload = {"text": text}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        log.info("sla_breach_notification_sent", contract=contract.name)
    except httpx.HTTPError as exc:
        log.error(
            "sla_breach_notification_failed",
            contract=contract.name,
            error=str(exc),
        )
