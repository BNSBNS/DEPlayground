"""Multi-format log parser.

Parses JSON, syslog (RFC 3164), and CEF (Common Event Format) log lines
into dicts suitable for normalization.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any


class ParseError(Exception):
    """Raised when a log line cannot be parsed."""


def parse_log_line(line: str) -> dict[str, Any]:
    """Auto-detect format and parse a log line.

    Tries JSON first (cheapest), then CEF, then syslog.
    Raises ParseError if no format matches.
    """
    line = line.strip()
    if not line:
        msg = "Empty log line"
        raise ParseError(msg)

    # JSON
    if line.startswith("{"):
        return parse_json(line)

    # CEF
    if line.startswith("CEF:"):
        return parse_cef(line)

    # Syslog (starts with month name)
    if _SYSLOG_RE.match(line):
        return parse_syslog(line)

    msg = f"Unrecognized log format: {line[:80]}"
    raise ParseError(msg)


def parse_json(line: str) -> dict[str, Any]:
    """Parse a JSON-formatted log line."""
    try:
        data: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e}"
        raise ParseError(msg) from e

    if not isinstance(data, dict):
        msg = "JSON log must be an object"
        raise ParseError(msg)
    return data


# Syslog RFC 3164 pattern:
# <priority>Mon DD HH:MM:SS hostname process[pid]: message
# or without priority: Mon DD HH:MM:SS hostname process[pid]: message
_SYSLOG_RE = re.compile(
    r"(?:<\d+>)?"
    r"(?P<month>[A-Z][a-z]{2})\s+"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+"
    r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+"
    r"(?P<message>.+)"
)

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def parse_syslog(line: str) -> dict[str, Any]:
    """Parse a syslog (RFC 3164) log line."""
    match = _SYSLOG_RE.match(line.strip())
    if not match:
        msg = f"Invalid syslog format: {line[:80]}"
        raise ParseError(msg)

    month = _MONTHS.get(match.group("month"), 1)
    day = int(match.group("day"))
    time_parts = match.group("time").split(":")
    # Use current year since syslog doesn't include it
    now = datetime.now(UTC)
    timestamp = datetime(
        now.year,
        month,
        day,
        int(time_parts[0]),
        int(time_parts[1]),
        int(time_parts[2]),
        tzinfo=UTC,
    )

    return {
        "timestamp": timestamp.isoformat(),
        "source": "syslog",
        "hostname": match.group("hostname"),
        "process": match.group("process"),
        "pid": match.group("pid"),
        "message": match.group("message"),
        "event_type": _classify_syslog_message(match.group("process"), match.group("message")),
        "severity": "info",
    }


def _classify_syslog_message(process: str, message: str) -> str:
    """Classify syslog message based on process and content."""
    lower_msg = message.lower()
    if process in ("sshd", "login", "su", "sudo"):
        if "failed" in lower_msg or "invalid" in lower_msg:
            return "login_failure"
        if "accepted" in lower_msg or "session opened" in lower_msg:
            return "login_success"
        return "auth_event"
    if "firewall" in lower_msg or "iptables" in lower_msg:
        return "firewall_event"
    if "dns" in process.lower() or "named" in process:
        return "dns_event"
    return "system_event"


# CEF format:
# CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension
_CEF_HEADER_RE = re.compile(
    r"CEF:(?P<version>\d+)\|"
    r"(?P<vendor>[^|]*)\|"
    r"(?P<product>[^|]*)\|"
    r"(?P<dev_version>[^|]*)\|"
    r"(?P<sig_id>[^|]*)\|"
    r"(?P<name>[^|]*)\|"
    r"(?P<severity>[^|]*)\|"
    r"(?P<extension>.*)"
)


def parse_cef(line: str) -> dict[str, Any]:
    """Parse a CEF (Common Event Format) log line."""
    match = _CEF_HEADER_RE.match(line.strip())
    if not match:
        msg = f"Invalid CEF format: {line[:80]}"
        raise ParseError(msg)

    # Parse extension key=value pairs
    extension = _parse_cef_extension(match.group("extension"))

    return {
        "timestamp": extension.pop("rt", datetime.now(UTC).isoformat()),
        "source": "cef",
        "event_type": match.group("name"),
        "severity": _map_cef_severity(match.group("severity")),
        "vendor": match.group("vendor"),
        "product": match.group("product"),
        "signature_id": match.group("sig_id"),
        "src_ip": extension.pop("src", None),
        "dst_ip": extension.pop("dst", None),
        "user": extension.pop("suser", extension.pop("duser", None)),
        "action": extension.pop("act", None),
        "details": extension,
    }


def _parse_cef_extension(ext_str: str) -> dict[str, str]:
    """Parse CEF extension key=value pairs."""
    result: dict[str, str] = {}
    if not ext_str.strip():
        return result
    # CEF extensions: key=value separated by spaces, values can contain spaces
    # Use a simple regex to split on key= patterns
    parts = re.split(r"\s+(?=\w+=)", ext_str.strip())
    for part in parts:
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip()] = value.strip()
    return result


def _map_cef_severity(severity_str: str) -> str:
    """Map CEF numeric severity (0-10) to text level."""
    try:
        level = int(severity_str)
    except ValueError:
        return severity_str.lower()

    if level >= 9:
        return "critical"
    if level >= 7:
        return "high"
    if level >= 4:
        return "medium"
    if level >= 1:
        return "low"
    return "info"
