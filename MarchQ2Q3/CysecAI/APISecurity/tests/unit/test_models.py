"""Tests for scanner models — Finding, Endpoint, ScanResult, enums."""

from __future__ import annotations

from src.models import (
    Endpoint,
    Finding,
    OWASPCategory,
    ScanResult,
    Severity,
)


class TestSeverity:
    def test_all_levels_defined(self) -> None:
        assert {s.value for s in Severity} == {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}

    def test_is_str_enum(self) -> None:
        assert Severity.CRITICAL == "CRITICAL"


class TestOWASPCategory:
    def test_all_ten_categories_defined(self) -> None:
        assert len(OWASPCategory) == 10

    def test_api1_value(self) -> None:
        assert "API1:2023" in OWASPCategory.API1_BOLA.value

    def test_api10_value(self) -> None:
        assert "API10:2023" in OWASPCategory.API10_CONSUMPTION.value


class TestFinding:
    def test_required_fields(self) -> None:
        f = Finding(
            owasp_category=OWASPCategory.API1_BOLA,
            title="BOLA in /users/{id}",
            severity=Severity.HIGH,
            endpoint="/api/v1/users/{user_id}",
            evidence="Accessed user 2 while authenticated as user 1",
            remediation="Verify resource ownership before returning data",
        )
        assert f.owasp_category == OWASPCategory.API1_BOLA
        assert f.severity == Severity.HIGH
        assert f.finding_id  # auto-generated UUID

    def test_finding_id_is_uuid(self) -> None:
        f = Finding(
            owasp_category=OWASPCategory.API2_AUTH,
            title="Weak JWT secret",
            severity=Severity.CRITICAL,
            endpoint="/api/v1/auth/login",
            evidence="Secret 'secret123' cracked in <1s",
            remediation="Use a cryptographically random 256-bit secret",
        )
        assert len(f.finding_id) == 36  # UUID format
        assert f.finding_id.count("-") == 4

    def test_timestamp_auto_set(self) -> None:
        f = Finding(
            owasp_category=OWASPCategory.API8_MISCONFIG,
            title="CORS wildcard",
            severity=Severity.MEDIUM,
            endpoint="/api/v1/users",
            evidence="Access-Control-Allow-Origin: *",
            remediation="Restrict CORS to known origins",
        )
        assert f.timestamp is not None

    def test_unique_ids(self) -> None:
        f1 = Finding(
            owasp_category=OWASPCategory.API1_BOLA,
            title="A",
            severity=Severity.LOW,
            endpoint="/",
            evidence="e",
            remediation="r",
        )
        f2 = Finding(
            owasp_category=OWASPCategory.API1_BOLA,
            title="B",
            severity=Severity.LOW,
            endpoint="/",
            evidence="e",
            remediation="r",
        )
        assert f1.finding_id != f2.finding_id


class TestEndpoint:
    def test_defaults(self) -> None:
        ep = Endpoint(path="/api/v1/users", method="GET")
        assert ep.requires_auth is False
        assert ep.parameters == []
        assert ep.description == ""

    def test_with_parameters(self) -> None:
        ep = Endpoint(
            path="/api/v1/users/{user_id}",
            method="GET",
            parameters=["user_id"],
            requires_auth=True,
        )
        assert "user_id" in ep.parameters
        assert ep.requires_auth is True


class TestScanResult:
    def _make_finding(self, title: str = "Test", severity: Severity = Severity.HIGH) -> Finding:
        return Finding(
            owasp_category=OWASPCategory.API1_BOLA,
            title=title,
            severity=severity,
            endpoint="/test",
            evidence="evidence",
            remediation="remediation",
        )

    def test_empty_scan_result(self) -> None:
        sr = ScanResult(target_url="http://localhost:8001")
        assert sr.findings == []
        assert sr.finding_count == 0
        assert sr.endpoints_scanned == 0

    def test_add_finding(self) -> None:
        sr = ScanResult(target_url="http://localhost:8001")
        sr.add_finding(self._make_finding())
        assert sr.finding_count == 1

    def test_critical_count(self) -> None:
        sr = ScanResult(target_url="http://localhost:8001")
        sr.add_finding(self._make_finding(severity=Severity.CRITICAL))
        sr.add_finding(self._make_finding(severity=Severity.CRITICAL))
        sr.add_finding(self._make_finding(severity=Severity.HIGH))
        assert sr.critical_count == 2
        assert sr.high_count == 1

    def test_scan_id_auto_generated(self) -> None:
        sr1 = ScanResult(target_url="http://a.com")
        sr2 = ScanResult(target_url="http://b.com")
        assert sr1.scan_id != sr2.scan_id

    def test_completed_at_optional(self) -> None:
        sr = ScanResult(target_url="http://localhost:8001")
        assert sr.completed_at is None
