"""Alert emitter — writes NetworkAlerts to disk as JSON."""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import NetworkAlert


def emit(alerts: list[NetworkAlert], output_path: str | pathlib.Path) -> int:
    """Write alerts to a JSON file. Returns the number of alerts written."""
    path = pathlib.Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "alert_id": a.alert_id,
            "rule_id": a.rule_id,
            "title": a.title,
            "severity": str(a.severity),
            "mitre_technique_id": a.mitre_technique_id,
            "source_ip": a.source_ip,
            "dest_ip": a.dest_ip,
            "timestamp": a.timestamp.isoformat(),
            "evidence": a.evidence,
            "packet_count": a.packet_count,
        }
        for a in alerts
    ]
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return len(records)
