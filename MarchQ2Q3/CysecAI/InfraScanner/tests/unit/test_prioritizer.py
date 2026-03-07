"""Tests for vulnerability prioritizer."""

from __future__ import annotations

from src.models import Dependency, Ecosystem, ScanFinding, Severity, Vulnerability
from src.scoring.prioritizer import (
    compute_priority_score,
    get_kev_findings,
    prioritize_findings,
    severity_summary,
)


def _make_finding(
    name: str,
    cvss: float | None = None,
    epss: float | None = None,
    is_kev: bool = False,
    severity: Severity = Severity.MEDIUM,
) -> ScanFinding:
    dep = Dependency(name=name, version="1.0", ecosystem=Ecosystem.PYPI)
    vuln = Vulnerability(
        vuln_id=f"CVE-{name}",
        cvss_score=cvss,
        epss_score=epss,
        is_kev=is_kev,
        severity=severity,
    )
    return ScanFinding(dependency=dep, vulnerabilities=[vuln])


class TestComputePriorityScore:
    def test_cvss_and_epss(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1", cvss_score=9.8, epss_score=0.5)
        score = compute_priority_score(vuln)
        assert abs(score - 0.49) < 0.001

    def test_kev_bonus(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1", cvss_score=5.0, epss_score=0.1, is_kev=True)
        score = compute_priority_score(vuln)
        # (0.5 × 0.1) + 0.3 = 0.35
        assert abs(score - 0.35) < 0.001

    def test_kev_capped_at_1(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1", cvss_score=10.0, epss_score=1.0, is_kev=True)
        score = compute_priority_score(vuln)
        assert score <= 1.0

    def test_no_cvss_zero(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1")
        assert compute_priority_score(vuln) == 0.0


class TestPrioritizeFindings:
    def test_sorted_by_risk(self) -> None:
        low = _make_finding("low", cvss=2.0, epss=0.01)
        high = _make_finding("high", cvss=9.8, epss=0.5)
        findings = prioritize_findings([low, high])
        assert findings[0].dependency.name == "high"

    def test_kev_prioritized(self) -> None:
        normal = _make_finding("normal", cvss=8.0, epss=0.1)
        kev = _make_finding("kev_pkg", cvss=4.0, epss=0.05, is_kev=True)
        findings = prioritize_findings([normal, kev])
        # KEV: (0.4 × 0.05) + 0.3 = 0.32, normal: (0.8 × 0.1) = 0.08 → KEV wins
        assert findings[0].dependency.name == "kev_pkg"

    def test_updates_risk_score(self) -> None:
        f = _make_finding("pkg", cvss=7.0, epss=0.2)
        prioritize_findings([f])
        assert f.risk_score > 0


class TestSeveritySummary:
    def test_counts_by_severity(self) -> None:
        f1 = _make_finding("a", severity=Severity.CRITICAL)
        f2 = _make_finding("b", severity=Severity.HIGH)
        summary = severity_summary([f1, f2])
        assert summary.get("CRITICAL") == 1
        assert summary.get("HIGH") == 1

    def test_empty_findings(self) -> None:
        assert severity_summary([]) == {}


class TestGetKevFindings:
    def test_returns_kev_only(self) -> None:
        kev = _make_finding("kev", is_kev=True)
        normal = _make_finding("normal", is_kev=False)
        pairs = get_kev_findings([kev, normal])
        assert len(pairs) == 1
        assert pairs[0][0].dependency.name == "kev"
