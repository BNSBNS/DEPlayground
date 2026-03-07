"""Parse AWS VPC Flow Log records into CloudEvent models."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from src.models import CloudEvent

# Default VPC flow log field order (v2 format)
_DEFAULT_FIELDS = [
    "version",
    "account_id",
    "interface_id",
    "srcaddr",
    "dstaddr",
    "srcport",
    "dstport",
    "protocol",
    "packets",
    "bytes",
    "start",
    "end",
    "action",
    "log_status",
]


def _parse_vpc_line(line: str, fields: list[str] | None = None) -> CloudEvent | None:
    """Parse a single space-separated VPC flow log line."""
    parts = line.strip().split()
    cols = fields or _DEFAULT_FIELDS
    if len(parts) < len(cols):
        return None
    row = dict(zip(cols, parts, strict=False))
    try:
        ts = datetime.datetime.fromtimestamp(int(row.get("start", "0")), tz=datetime.UTC)
    except (ValueError, OSError):
        ts = datetime.datetime.now(datetime.UTC)
    try:
        src_port = int(row.get("srcport", "0"))
    except ValueError:
        src_port = None
    try:
        dst_port = int(row.get("dstport", "0"))
    except ValueError:
        dst_port = None
    try:
        transferred = int(row.get("bytes", "0"))
    except ValueError:
        transferred = 0
    return CloudEvent(
        timestamp=ts,
        event_source="vpc_flow",
        src_addr=row.get("srcaddr"),
        dst_addr=row.get("dstaddr"),
        src_port=src_port,
        dst_port=dst_port,
        action=row.get("action"),
        bytes_transferred=transferred,
        extra={"protocol": row.get("protocol", ""), "interface": row.get("interface_id", "")},
    )


def parse_vpc_flow_lines(lines: list[str], fields: list[str] | None = None) -> list[CloudEvent]:
    """Parse VPC flow log lines (space-separated). Skips header and blank lines."""
    events: list[CloudEvent] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("version"):
            continue
        event = _parse_vpc_line(stripped, fields)
        if event is not None:
            events.append(event)
    return events


def parse_vpc_flow_json(data: list[dict[str, Any]]) -> list[CloudEvent]:
    """Parse VPC flow records from a list of dicts (JSON format)."""
    events: list[CloudEvent] = []
    for row in data:
        try:
            ts = datetime.datetime.fromtimestamp(int(row.get("start", 0)), tz=datetime.UTC)
        except (ValueError, OSError):
            ts = datetime.datetime.now(datetime.UTC)
        events.append(
            CloudEvent(
                timestamp=ts,
                event_source="vpc_flow",
                src_addr=row.get("srcaddr"),
                dst_addr=row.get("dstaddr"),
                src_port=row.get("srcport"),
                dst_port=row.get("dstport"),
                action=row.get("action"),
                bytes_transferred=int(row.get("bytes", 0)),
                extra={"protocol": str(row.get("protocol", ""))},
            )
        )
    return events


def load_vpc_flow(path: str | pathlib.Path) -> list[CloudEvent]:
    """Load VPC flow logs from either JSON or text file."""
    content = pathlib.Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return parse_vpc_flow_json(data)
    except json.JSONDecodeError:
        pass
    return parse_vpc_flow_lines(content.splitlines())
