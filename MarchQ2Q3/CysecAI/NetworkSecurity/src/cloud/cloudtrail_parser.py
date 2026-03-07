"""Parse AWS CloudTrail JSON log records into CloudEvent models."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from src.models import CloudEvent


def _parse_record(record: dict[str, Any]) -> CloudEvent:
    raw_time = record.get("eventTime", "")
    try:
        ts = datetime.datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        ts = datetime.datetime.now(datetime.UTC)
    identity = record.get("userIdentity", {})
    user = identity.get("arn") or identity.get("userName") or identity.get("type", "unknown")
    return CloudEvent(
        timestamp=ts,
        event_source="cloudtrail",
        event_name=record.get("eventName"),
        source_ip=record.get("sourceIPAddress"),
        user_identity=str(user),
        error_code=record.get("errorCode"),
        extra={
            "eventSource": record.get("eventSource", ""),
            "awsRegion": record.get("awsRegion", ""),
            "requestParameters": record.get("requestParameters", {}),
        },
    )


def parse_cloudtrail(data: list[dict[str, Any]]) -> list[CloudEvent]:
    """Parse a list of CloudTrail record dicts into CloudEvent objects."""
    return [_parse_record(r) for r in data]


def load_cloudtrail(path: str | pathlib.Path) -> list[CloudEvent]:
    """Load CloudTrail records from a JSON file."""
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = raw.get("Records", raw) if isinstance(raw, dict) else raw
    return parse_cloudtrail(records)
