"""SecurityAlert consumer for cross-project alert integration.

Deserializes SecurityAlert messages (Foundations #8 schema) from JSON,
typically consumed from Kafka topic `cysec.alerts`. This module handles
deserialization only — Kafka transport is added in Phase 5.
"""

from __future__ import annotations

import json
from typing import Any

from cysec_shared import SecurityAlert
from src.ingestion.normalizer import NormalizedEvent


class AlertDeserializationError(Exception):
    """Raised when a SecurityAlert message cannot be deserialized."""


def deserialize_alert(data: str | bytes | dict[str, Any]) -> SecurityAlert:
    """Deserialize a SecurityAlert from JSON string, bytes, or dict.

    Raises AlertDeserializationError on invalid input.
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    if isinstance(data, str):
        try:
            parsed: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON for SecurityAlert: {e}"
            raise AlertDeserializationError(msg) from e
    else:
        parsed = data

    try:
        return SecurityAlert(**parsed)
    except Exception as e:
        msg = f"Invalid SecurityAlert schema: {e}"
        raise AlertDeserializationError(msg) from e


def alert_to_normalized_event(alert: SecurityAlert) -> NormalizedEvent:
    """Convert a SecurityAlert into a NormalizedEvent for unified processing.

    This allows the detection/correlation engine to treat cross-project
    alerts the same as locally generated events.
    """
    return NormalizedEvent(
        event_id=alert.alert_id,
        timestamp=alert.timestamp,
        source=f"alert:{alert.source_project}",
        event_type=f"security_alert:{alert.rule_id}",
        severity=alert.severity,
        src_ip=alert.source_ip,
        dst_ip=alert.dest_ip,
        user=alert.user,
        action="alert",
        hostname=alert.affected_asset,
        details={
            "title": alert.title,
            "description": alert.description,
            "mitre_technique_id": alert.mitre_technique_id,
            "mitre_tactic": alert.mitre_tactic,
            "evidence": alert.evidence,
            "recommendations": alert.recommendations,
        },
    )
