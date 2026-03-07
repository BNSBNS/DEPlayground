"""Alert emitter — convert scan findings to structured alert JSON and persist to disk."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.models import Finding, ScanResult


def emit(
    scan_result: ScanResult,
    output_path: str | pathlib.Path,
) -> int:
    """Write findings as alert entries to a JSON file.

    Returns the number of alerts written.
    """
    alerts = [_finding_to_alert(f) for f in scan_result.findings]
    payload: dict[str, Any] = {
        "scan_id": scan_result.scan_id,
        "target": scan_result.target_url,
        "emitted_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "finding_count": len(alerts),
        "alerts": alerts,
    }
    path = pathlib.Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(alerts)


def _finding_to_alert(finding: Finding) -> dict[str, str]:
    return {
        "id": finding.finding_id,
        "timestamp": finding.timestamp.isoformat(),
        "severity": str(finding.severity),
        "category": str(finding.owasp_category),
        "title": finding.title,
        "endpoint": finding.endpoint,
        "method": finding.method,
        "evidence": finding.evidence,
        "remediation": finding.remediation,
    }
