"""Tests for core data models."""

from __future__ import annotations

import datetime

from src.models import (
    Dependency,
    DockerFinding,
    Ecosystem,
    LicenseFinding,
    LicenseRisk,
    SBOMComponent,
    ScanFinding,
    ScanResult,
    Severity,
    TyposquatFinding,
    Vulnerability,
)


class TestDependency:
    def test_name_required(self) -> None:
        dep = Dependency(name="requests", version="2.28.0", ecosystem=Ecosystem.PYPI)
        assert dep.name == "requests"

    def test_version_optional(self) -> None:
        dep = Dependency(name="flask", ecosystem=Ecosystem.PYPI)
        assert dep.version is None

    def test_ecosystem_values(self) -> None:
        for eco in Ecosystem:
            dep = Dependency(name="pkg", ecosystem=eco)
            assert dep.ecosystem == eco


class TestVulnerability:
    def test_defaults(self) -> None:
        v = Vulnerability(vuln_id="CVE-2023-0001")
        assert v.severity == Severity.UNKNOWN
        assert v.is_kev is False
        assert v.cvss_score is None

    def test_all_fields(self) -> None:
        v = Vulnerability(
            vuln_id="CVE-2023-0001",
            description="Test vuln",
            cvss_score=9.8,
            severity=Severity.CRITICAL,
            epss_score=0.75,
            is_kev=True,
        )
        assert v.cvss_score == 9.8
        assert v.is_kev is True


class TestScanResult:
    def test_total_vulns_property(self) -> None:
        dep = Dependency(name="pkg", version="1.0", ecosystem=Ecosystem.PYPI)
        vuln = Vulnerability(vuln_id="CVE-2023-0001", severity=Severity.HIGH)
        finding = ScanFinding(dependency=dep, vulnerabilities=[vuln])
        result = ScanResult(target_path="/test", findings=[finding])
        assert result.total_vulns == 1

    def test_critical_count(self) -> None:
        dep = Dependency(name="pkg", version="1.0", ecosystem=Ecosystem.PYPI)
        critical = Vulnerability(vuln_id="CVE-1", severity=Severity.CRITICAL)
        high = Vulnerability(vuln_id="CVE-2", severity=Severity.HIGH)
        finding = ScanFinding(dependency=dep, vulnerabilities=[critical, high])
        result = ScanResult(target_path="/test", findings=[finding])
        assert result.critical_count == 1
        assert result.high_count == 1

    def test_to_dict_keys(self) -> None:
        result = ScanResult(target_path="/test")
        d = result.to_dict()
        for key in ("scan_id", "target_path", "total_vulnerabilities", "critical"):
            assert key in d

    def test_scan_id_unique(self) -> None:
        r1 = ScanResult(target_path="/a")
        r2 = ScanResult(target_path="/b")
        assert r1.scan_id != r2.scan_id

    def test_timestamp_utc(self) -> None:
        result = ScanResult(target_path="/test")
        assert result.timestamp.tzinfo == datetime.UTC


class TestDockerFinding:
    def test_fields(self) -> None:
        df = DockerFinding(
            check_id="DKR-001",
            description="Running as root",
            severity=Severity.HIGH,
            line_number=5,
        )
        assert df.check_id == "DKR-001"
        assert df.line_number == 5


class TestSBOMComponent:
    def test_bom_ref_auto(self) -> None:
        c1 = SBOMComponent(name="requests", version="2.28.0")
        c2 = SBOMComponent(name="requests", version="2.28.0")
        assert c1.bom_ref != c2.bom_ref

    def test_purl_field(self) -> None:
        c = SBOMComponent(name="pkg", version="1.0", purl="pkg:pypi/pkg@1.0")
        assert c.purl == "pkg:pypi/pkg@1.0"


class TestTyposquatFinding:
    def test_fields(self) -> None:
        t = TyposquatFinding(
            package="requsets", similar_to="requests", distance=1, ecosystem=Ecosystem.PYPI
        )
        assert t.distance == 1


class TestLicenseFinding:
    def test_copyleft_risk(self) -> None:
        lf = LicenseFinding(package="libgpl", license_id="GPL-3.0", risk=LicenseRisk.COPYLEFT)
        assert lf.risk == LicenseRisk.COPYLEFT
