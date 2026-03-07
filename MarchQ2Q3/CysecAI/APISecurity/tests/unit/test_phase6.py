"""Tests for Phase 6: Inventory + Consumption Testers + Alert Emitter + Reports."""

from __future__ import annotations

import json
import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.alerts.emitter import emit
from src.models import Endpoint, Finding, OWASPCategory, ScanResult, Severity
from src.reports.json_report import generate_json_report, write_json_report
from src.reports.sarif import generate_sarif, write_sarif
from src.testers.consumption_tester import ConsumptionTester, _flatten_keys
from src.testers.inventory_tester import InventoryTester, _legacy_paths

# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def scan_result() -> ScanResult:
    return ScanResult(target_url="http://localhost:8001")


@pytest.fixture()
def populated_result() -> ScanResult:
    result = ScanResult(target_url="http://localhost:8001")
    result.endpoints_scanned = 10
    result.add_finding(
        Finding(
            owasp_category=OWASPCategory.API1_BOLA,
            title="Test BOLA finding",
            severity=Severity.HIGH,
            endpoint="/api/v1/users/2",
            method="GET",
            evidence="User A accessed User B's data",
            remediation="Add object-level auth checks.",
        )
    )
    result.add_finding(
        Finding(
            owasp_category=OWASPCategory.API8_MISCONFIG,
            title="Missing HSTS header",
            severity=Severity.MEDIUM,
            endpoint="/api/v1/users/1",
            method="GET",
            evidence="Header absent",
            remediation="Add HSTS.",
        )
    )
    return result


# ── InventoryTester helpers ───────────────────────────────────────────────────


class TestLegacyPaths:
    def test_generates_older_version(self) -> None:
        paths = _legacy_paths("/api/v1/users/{user_id}")
        assert any("v0" in p for p in paths)

    def test_strips_api_prefix(self) -> None:
        paths = _legacy_paths("/api/v1/users")
        assert "/v1/users" in paths

    def test_no_version_returns_empty(self) -> None:
        assert _legacy_paths("/api/users") == []

    def test_no_api_prefix_no_strip(self) -> None:
        paths = _legacy_paths("/v1/users")
        # No /api/ to strip, so should only contain older versions
        assert all("/api/" not in p for p in paths)


# ── InventoryTester ───────────────────────────────────────────────────────────


class TestInventoryTester:
    @pytest.mark.asyncio
    async def test_shadow_path_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"users": []}'
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InventoryTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        shadow_findings = [
            f for f in scan_result.findings if "Shadow" in f.title or "Legacy" in f.title
        ]
        assert len(shadow_findings) > 0
        assert shadow_findings[0].owasp_category == OWASPCategory.API9_INVENTORY
        assert shadow_findings[0].severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_404_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InventoryTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_405_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 405
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InventoryTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_http_error_no_crash(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = InventoryTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_legacy_endpoint_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"id": 1}'
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InventoryTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users/{user_id}", method="GET")
        await tester.test_endpoint(endpoint, scan_result)

        legacy_findings = [f for f in scan_result.findings if "Legacy" in f.title]
        assert len(legacy_findings) > 0

    @pytest.mark.asyncio
    async def test_no_version_endpoint_no_legacy_requests(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()

        tester = InventoryTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/users", method="GET")  # no version in path
        await tester.test_endpoint(endpoint, scan_result)

        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_500_still_detected(self, scan_result: ScanResult) -> None:
        """A 500 on a shadow path still means it exists — should be flagged."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InventoryTester(mock_client, "http://localhost:8001")
        await tester._probe("/v1/users", "Legacy", scan_result)

        assert scan_result.finding_count == 1


# ── ConsumptionTester helpers ─────────────────────────────────────────────────


class TestFlattenKeys:
    def test_flat_dict(self) -> None:
        keys = _flatten_keys({"name": "alice", "age": 30})
        assert "name" in keys
        assert "age" in keys

    def test_nested_dict(self) -> None:
        keys = _flatten_keys({"user": {"password": "x"}})
        assert "password" in keys

    def test_list_of_dicts(self) -> None:
        keys = _flatten_keys([{"id": 1, "secret": "x"}, {"id": 2}])
        assert "secret" in keys
        assert "id" in keys

    def test_empty(self) -> None:
        assert _flatten_keys({}) == set()

    def test_non_dict_non_list(self) -> None:
        assert _flatten_keys("string") == set()


# ── ConsumptionTester ─────────────────────────────────────────────────────────


class TestConsumptionTester:
    @pytest.mark.asyncio
    async def test_unpaginated_list_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # 10 users, no pagination fields
        mock_resp.json.return_value = {"users": [{"id": i, "username": f"u{i}"} for i in range(10)]}
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET")
        await tester.test_endpoint(endpoint, scan_result)

        pagination_findings = [f for f in scan_result.findings if "pagination" in f.title.lower()]
        assert len(pagination_findings) > 0
        assert pagination_findings[0].owasp_category == OWASPCategory.API10_CONSUMPTION
        assert pagination_findings[0].severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_paginated_list_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "users": [{"id": i} for i in range(10)],
            "total": 10,
            "page": 1,
            "limit": 20,
        }
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET")
        await tester.test_endpoint(endpoint, scan_result)

        pagination_findings = [f for f in scan_result.findings if "pagination" in f.title.lower()]
        assert len(pagination_findings) == 0

    @pytest.mark.asyncio
    async def test_sensitive_field_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"users": [{"id": 1, "password": "hash123"}]}
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET")
        await tester.test_endpoint(endpoint, scan_result)

        sensitive_findings = [f for f in scan_result.findings if "Sensitive fields" in f.title]
        assert len(sensitive_findings) > 0
        assert sensitive_findings[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_small_list_no_pagination_finding(self, scan_result: ScanResult) -> None:
        """Fewer than threshold items — no pagination finding."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"users": [{"id": 1}, {"id": 2}]}  # only 2 items
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET")
        await tester.test_endpoint(endpoint, scan_result)

        pagination_findings = [f for f in scan_result.findings if "pagination" in f.title.lower()]
        assert len(pagination_findings) == 0

    @pytest.mark.asyncio
    async def test_non_get_skipped(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="POST")
        await tester.test_endpoint(endpoint, scan_result)

        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_no_crash(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_non_200_skipped(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = ConsumptionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET")
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0


# ── Alert Emitter ─────────────────────────────────────────────────────────────


class TestAlertEmitter:
    def test_emit_creates_file(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "alerts.json"
            count = emit(populated_result, out)

            assert out.exists()
            assert count == 2  # two findings in populated_result

    def test_emit_valid_json(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "alerts.json"
            emit(populated_result, out)

            data = json.loads(out.read_text())
            assert "alerts" in data
            assert len(data["alerts"]) == 2

    def test_emit_alert_fields(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "alerts.json"
            emit(populated_result, out)

            data = json.loads(out.read_text())
            alert = data["alerts"][0]
            for field in ("id", "timestamp", "severity", "category", "title", "endpoint"):
                assert field in alert

    def test_emit_zero_findings(self, scan_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "alerts.json"
            count = emit(scan_result, out)

            assert count == 0
            data = json.loads(out.read_text())
            assert data["alerts"] == []

    def test_emit_creates_parent_dirs(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "nested" / "dir" / "alerts.json"
            emit(populated_result, out)

            assert out.exists()

    def test_emit_returns_count(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "alerts.json"
            assert emit(populated_result, out) == 2


# ── SARIF Report ──────────────────────────────────────────────────────────────


class TestSarifReport:
    def test_sarif_version(self, populated_result: ScanResult) -> None:
        sarif = generate_sarif(populated_result)
        assert sarif["version"] == "2.1.0"

    def test_sarif_has_runs(self, populated_result: ScanResult) -> None:
        sarif = generate_sarif(populated_result)
        assert len(sarif["runs"]) == 1

    def test_sarif_results_count(self, populated_result: ScanResult) -> None:
        sarif = generate_sarif(populated_result)
        assert len(sarif["runs"][0]["results"]) == 2

    def test_sarif_result_fields(self, populated_result: ScanResult) -> None:
        sarif = generate_sarif(populated_result)
        result = sarif["runs"][0]["results"][0]
        assert "ruleId" in result
        assert "level" in result
        assert "message" in result
        assert "locations" in result

    def test_sarif_severity_mapping(self, populated_result: ScanResult) -> None:
        sarif = generate_sarif(populated_result)
        results = {r["ruleId"]: r["level"] for r in sarif["runs"][0]["results"]}
        # HIGH → error
        assert results.get("API1:2023") == "error"
        # MEDIUM → warning
        assert results.get("API8:2023") == "warning"

    def test_sarif_unique_rules(self, populated_result: ScanResult) -> None:
        sarif = generate_sarif(populated_result)
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = [r["id"] for r in rules]
        assert len(rule_ids) == len(set(rule_ids))  # no duplicates

    def test_sarif_empty_result(self, scan_result: ScanResult) -> None:
        sarif = generate_sarif(scan_result)
        assert sarif["runs"][0]["results"] == []
        assert sarif["runs"][0]["tool"]["driver"]["rules"] == []

    def test_write_sarif_creates_file(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "report.sarif"
            write_sarif(populated_result, out)

            assert out.exists()
            data = json.loads(out.read_text())
            assert data["version"] == "2.1.0"


# ── JSON Report ───────────────────────────────────────────────────────────────


class TestJsonReport:
    def test_report_fields(self, populated_result: ScanResult) -> None:
        report = generate_json_report(populated_result)
        for field in (
            "scan_id",
            "target_url",
            "started_at",
            "endpoints_scanned",
            "finding_count",
            "critical_count",
            "high_count",
            "findings",
        ):
            assert field in report

    def test_finding_count_matches(self, populated_result: ScanResult) -> None:
        report = generate_json_report(populated_result)
        assert report["finding_count"] == 2
        assert len(report["findings"]) == 2

    def test_severity_counts(self, populated_result: ScanResult) -> None:
        report = generate_json_report(populated_result)
        assert report["high_count"] == 1
        assert report["critical_count"] == 0

    def test_finding_fields(self, populated_result: ScanResult) -> None:
        report = generate_json_report(populated_result)
        finding = report["findings"][0]
        for field in (
            "finding_id",
            "owasp_category",
            "title",
            "severity",
            "endpoint",
            "method",
            "evidence",
            "remediation",
            "timestamp",
        ):
            assert field in finding

    def test_completed_at_none_when_not_set(self, scan_result: ScanResult) -> None:
        report = generate_json_report(scan_result)
        assert report["completed_at"] is None

    def test_write_json_report_creates_file(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "report.json"
            write_json_report(populated_result, out)

            assert out.exists()
            data = json.loads(out.read_text())
            assert data["finding_count"] == 2

    def test_write_creates_parent_dirs(self, populated_result: ScanResult) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = pathlib.Path(tmpdir) / "deep" / "path" / "report.json"
            write_json_report(populated_result, out)

            assert out.exists()
