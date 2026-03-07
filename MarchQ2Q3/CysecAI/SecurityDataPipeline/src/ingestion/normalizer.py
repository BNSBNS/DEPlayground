"""Normalized event model and normalization logic.

All log sources are normalized to a common NormalizedEvent schema,
enabling uniform detection and correlation regardless of source format.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedEvent(BaseModel):
    """Common event schema — all log formats normalize to this.

    Fields align with ECS (Elastic Common Schema) core fields.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    source: str
    event_type: str
    severity: str = "info"
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    user: str | None = None
    action: str | None = None
    protocol: str | None = None
    hostname: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    raw: str | None = None  # original log line for audit


def normalize_from_log_event(event_dict: dict[str, Any]) -> NormalizedEvent:
    """Normalize an internal LogEvent dict to NormalizedEvent."""
    details = event_dict.get("details", {})
    return NormalizedEvent(
        event_id=event_dict.get("event_id", str(uuid.uuid4())),
        timestamp=_parse_timestamp(event_dict.get("timestamp", "")),
        source=event_dict.get("source", "unknown"),
        event_type=event_dict.get("event_type", "unknown"),
        severity=event_dict.get("severity", "info"),
        src_ip=event_dict.get("src_ip"),
        dst_ip=event_dict.get("dst_ip"),
        dst_port=details.get("dst_port"),
        user=event_dict.get("user"),
        action=event_dict.get("action"),
        protocol=details.get("protocol"),
        hostname=details.get("host"),
        details=details,
    )


def _parse_timestamp(value: Any) -> datetime:
    """Parse timestamp from various formats."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        # ISO format
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)
