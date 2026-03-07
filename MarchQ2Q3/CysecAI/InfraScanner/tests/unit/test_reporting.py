"""Tests for reporting modules."""

from __future__ import annotations

import json

from src.models import (
    Dependency,
    DockerFinding,
    Ecosystem,
    ScanFinding,
    ScanResult,
    Severity,
    Vulnerability,
)
from src.reporting.ci_output import to_json, to_sarif
from src.reporting.html_report import generate_html_report


def _make_result(with_vuln: bool = True) -> ScanResult:
    dep = Dependency(name="requests", version="2.18.4", ecosystem=Ecosystem.PYPI)
    result = ScanResult(target_path="/test/project")
    result.dependencies = [dep]
    if with_vuln:
        vuln = Vulnerability(
            vuln_id="CVE-2023-32681",
            description="Auth header leak",
            cvss_score=7.2,
            severity=Severity.HIGH,
        )
        result.findings = [ScanFinding(dependency=dep, vulnerabilities=[vuln])]
    return result


class TestToJson:
    def test_valid_json(self) -> None:
        result = _make_result()
        output = to_json(result)
        parsed = json.loads(output)
        assert "scan_id" in parsed

    def test_has_findings(self) -> None:
        result = _make_result()
        output = to_json(result)
        parsed = json.loads(output)
        assert len(parsed["findings"]) == 1

    def test_empty_result(self) -> None:
        result = _make_result(with_vuln=False)
        output = to_json(result)
        parsed = json.loads(output)
        assert parsed["total_vulnerabilities"] == 0


class TestToSarif:
    def test_sarif_version(self) -> None:
        sarif = to_sarif(_make_result())
        assert sarif["version"] == "2.1.0"

    def test_has_runs(self) -> None:
        sarif = to_sarif(_make_result())
        assert len(sarif["runs"]) == 1

    def test_tool_name(self) -> None:
        sarif = to_sarif(_make_result())
        assert sarif["runs"][0]["tool"]["driver"]["name"] == "InfraScanner"

    def test_rules_populated(self) -> None:
        sarif = to_sarif(_make_result())
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) >= 1

    def test_results_populated(self) -> None:
        sarif = to_sarif(_make_result())
        results = sarif["runs"][0]["results"]
        assert len(results) >= 1

    def test_docker_findings_in_sarif(self) -> None:
        result = _make_result(with_vuln=False)
        result.docker_findings = [
            DockerFinding(
                check_id="DKR-001",
                description="Root user",
                severity=Severity.HIGH,
            )
        ]
        sarif = to_sarif(result)
        results = sarif["runs"][0]["results"]
        assert len(results) == 1

    def test_empty_result_no_rules(self) -> None:
        result = _make_result(with_vuln=False)
        sarif = to_sarif(result)
        assert sarif["runs"][0]["tool"]["driver"]["rules"] == []


class TestGenerateHtmlReport:
    def test_returns_html_string(self) -> None:
        result = _make_result()
        html = generate_html_report(result)
        assert "<html" in html.lower()

    def test_contains_package_name(self) -> None:
        result = _make_result()
        html = generate_html_report(result)
        assert "requests" in html

    def test_contains_cve_id(self) -> None:
        result = _make_result()
        html = generate_html_report(result)
        assert "CVE-2023-32681" in html

    def test_empty_result_renders(self) -> None:
        result = _make_result(with_vuln=False)
        html = generate_html_report(result)
        assert "<html" in html.lower()
