"""Tests for vulnerability matcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.models import Dependency, Ecosystem, Severity, Vulnerability
from src.vuln_db.matcher import _compute_risk, match_vulnerabilities, severity_from_score
from src.vuln_db.osv_client import OSVClient


class TestComputeRisk:
    def test_with_cvss_and_epss(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1", cvss_score=7.5, epss_score=0.1)
        score = _compute_risk([vuln])
        assert abs(score - 0.075) < 0.001

    def test_no_epss_uses_default(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1", cvss_score=5.0)
        score = _compute_risk([vuln])
        # default epss = 0.1: 0.5 × 0.1 = 0.05
        assert abs(score - 0.05) < 0.001

    def test_no_cvss_zero_score(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-1")
        assert _compute_risk([vuln]) == 0.0

    def test_returns_max_over_multiple_vulns(self) -> None:
        v1 = Vulnerability(vuln_id="CVE-1", cvss_score=3.0, epss_score=0.5)
        v2 = Vulnerability(vuln_id="CVE-2", cvss_score=9.0, epss_score=0.5)
        score = _compute_risk([v1, v2])
        assert score > 0.4


class TestSeverityFromScore:
    def test_critical(self) -> None:
        assert severity_from_score(9.0) == Severity.CRITICAL
        assert severity_from_score(10.0) == Severity.CRITICAL

    def test_high(self) -> None:
        assert severity_from_score(7.0) == Severity.HIGH
        assert severity_from_score(8.5) == Severity.HIGH

    def test_medium(self) -> None:
        assert severity_from_score(4.0) == Severity.MEDIUM
        assert severity_from_score(6.9) == Severity.MEDIUM

    def test_low(self) -> None:
        assert severity_from_score(0.1) == Severity.LOW

    def test_none(self) -> None:
        assert severity_from_score(0.0) == Severity.NONE


class TestMatchVulnerabilities:
    async def test_no_vulns_returns_empty(self) -> None:
        mock_client = AsyncMock(spec=OSVClient)
        mock_client.query_batch.return_value = {}
        deps = [Dependency(name="safe-pkg", version="1.0", ecosystem=Ecosystem.PYPI)]
        findings = await match_vulnerabilities(deps, mock_client)
        assert findings == []

    async def test_vulnerability_matched(self) -> None:
        vuln = Vulnerability(vuln_id="CVE-2023-0001", cvss_score=7.5, epss_score=0.1)
        mock_client = AsyncMock(spec=OSVClient)
        mock_client.query_batch.return_value = {0: [vuln]}
        deps = [Dependency(name="requests", version="2.18.4", ecosystem=Ecosystem.PYPI)]
        findings = await match_vulnerabilities(deps, mock_client)
        assert len(findings) == 1
        assert findings[0].dependency.name == "requests"
        assert findings[0].risk_score > 0

    async def test_uses_default_client_when_none(self) -> None:
        # Should not raise even with no client provided
        deps: list[Dependency] = []
        with patch("src.vuln_db.matcher.OSVClient") as MockOSV:
            instance = AsyncMock()
            instance.query_batch.return_value = {}
            MockOSV.return_value = instance
            findings = await match_vulnerabilities(deps)
            assert findings == []
