"""Emit scan findings as SecurityAlert-compatible JSON (Foundations #8 schema)."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from src.models import ScanFinding, ScanResult, Severity


def _severity_to_alert_severity(sev: Severity) -> str:
    """Map Severity to the common alert schema severity string."""
    return str(sev).upper()


def finding_to_alert(finding: ScanFinding, scan_id: str = "") -> dict[str, Any]:
    """Convert a ScanFinding to a SecurityAlert dict (Foundations #8 schema)."""
    top_vuln = max(finding.vulnerabilities, key=lambda v: v.cvss_score or 0.0)
    return {
        "alert_id": f"{scan_id}:{finding.dependency.name}:{top_vuln.vuln_id}",
        "rule_id": "dependency_vulnerability",
        "title": f"Vulnerable dependency: {finding.dependency.name}@{finding.dependency.version}",
        "severity": _severity_to_alert_severity(top_vuln.severity),
        "mitre_technique_id": "T1195.001",  # Supply Chain Compromise: Compromise Software Deps
        "source": str(finding.dependency.ecosystem),
        "evidence": (f"{top_vuln.vuln_id} — {top_vuln.description[:200]}"),
        "cvss_score": top_vuln.cvss_score,
        "epss_score": top_vuln.epss_score,
        "is_kev": top_vuln.is_kev,
        "risk_score": finding.risk_score,
        "package": finding.dependency.name,
        "version": finding.dependency.version,
    }


def emit_alerts(result: ScanResult, output_path: pathlib.Path) -> int:
    """Write all scan findings as JSON alerts to output_path.

    Returns count of alerts written.
    """
    alerts = [finding_to_alert(f, scan_id=result.scan_id) for f in result.findings]
    output_path.write_text(json.dumps(alerts, indent=2), encoding="utf-8")
    return len(alerts)
