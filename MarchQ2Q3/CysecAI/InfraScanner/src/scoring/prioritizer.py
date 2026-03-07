"""Prioritize vulnerabilities by CVSS × EPSS score; flag CISA KEV entries."""

from __future__ import annotations

from src.models import ScanFinding, Severity, Vulnerability


def compute_priority_score(vuln: Vulnerability) -> float:
    """Compute a priority score for a single vulnerability.

    Formula: CVSS_normalised × EPSS_probability
    - CVSS_normalised = base_score / 10.0  (range 0–1)
    - EPSS_probability = 0–1 (default 0.1 if unknown)
    - CISA KEV bonus: +0.3 additive, capped at 1.0
    """
    cvss = (vuln.cvss_score or 0.0) / 10.0
    epss = vuln.epss_score if vuln.epss_score is not None else 0.1
    score = cvss * epss
    if vuln.is_kev:
        score = min(1.0, score + 0.3)
    return round(score, 4)


def prioritize_findings(findings: list[ScanFinding]) -> list[ScanFinding]:
    """Sort findings by descending priority score (highest risk first)."""
    for finding in findings:
        # Recompute risk_score using per-vuln scoring
        scores = [compute_priority_score(v) for v in finding.vulnerabilities]
        finding.risk_score = max(scores) if scores else 0.0

    return sorted(findings, key=lambda f: f.risk_score, reverse=True)


def get_kev_findings(findings: list[ScanFinding]) -> list[tuple[ScanFinding, Vulnerability]]:
    """Return all (finding, vuln) pairs that are in the CISA KEV catalog."""
    return [(f, v) for f in findings for v in f.vulnerabilities if v.is_kev]


def severity_summary(findings: list[ScanFinding]) -> dict[str, int]:
    """Return a count of vulnerabilities by severity across all findings."""
    counts: dict[str, int] = dict.fromkeys(Severity, 0)
    for f in findings:
        for v in f.vulnerabilities:
            counts[str(v.severity)] = counts.get(str(v.severity), 0) + 1
    return {k: v for k, v in counts.items() if v > 0}
