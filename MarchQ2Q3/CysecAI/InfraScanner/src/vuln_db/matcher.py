"""Match dependencies to known vulnerabilities using OSV + optional NVD enrichment."""

from __future__ import annotations

from src.models import Dependency, ScanFinding, Severity, Vulnerability
from src.vuln_db.osv_client import OSVClient


async def match_vulnerabilities(
    dependencies: list[Dependency],
    osv_client: OSVClient | None = None,
) -> list[ScanFinding]:
    """Query OSV for each dependency and return ScanFindings with matched vulns."""
    if osv_client is None:
        osv_client = OSVClient()

    # Batch query — one HTTP call for all deps
    results = await osv_client.query_batch(dependencies)

    findings: list[ScanFinding] = []
    for idx, dep in enumerate(dependencies):
        vulns = results.get(idx, [])
        if vulns:
            findings.append(
                ScanFinding(
                    dependency=dep,
                    vulnerabilities=vulns,
                    risk_score=_compute_risk(vulns),
                )
            )
    return findings


def _compute_risk(vulns: list[Vulnerability]) -> float:
    """Compute risk score as max(CVSS × EPSS). Falls back to CVSS/10 if no EPSS."""
    best = 0.0
    for v in vulns:
        if v.cvss_score is not None:
            cvss = v.cvss_score / 10.0
            epss = v.epss_score if v.epss_score is not None else 0.1
            score = cvss * epss
            best = max(best, score)
    return round(best, 4)


def severity_from_score(cvss: float) -> Severity:
    """Map a CVSS base score to a Severity level."""
    if cvss >= 9.0:
        return Severity.CRITICAL
    if cvss >= 7.0:
        return Severity.HIGH
    if cvss >= 4.0:
        return Severity.MEDIUM
    if cvss > 0:
        return Severity.LOW
    return Severity.NONE
