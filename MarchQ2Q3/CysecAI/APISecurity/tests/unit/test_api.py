"""Tests for the FastAPI scanner API and scanner orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Reset the in-memory scan store before each test
import src.api.routers.scans as scans_module
from src.api.main import app
from src.models import Finding, OWASPCategory, ScanResult, Severity


@pytest.fixture(autouse=True)
def clear_scans() -> None:
    scans_module._scans.clear()


@pytest.fixture(autouse=True)
def no_bg_scan() -> object:
    """Prevent background scan tasks from making real HTTP calls in unit tests."""

    async def _noop(*_args: object, **_kwargs: object) -> None:
        pass

    with patch("src.api.routers.scans._run_scan_bg", side_effect=_noop):
        yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def completed_result() -> ScanResult:
    result = ScanResult(target_url="http://localhost:8001")
    result.endpoints_scanned = 5
    result.add_finding(
        Finding(
            owasp_category=OWASPCategory.API8_MISCONFIG,
            title="Missing HSTS",
            severity=Severity.MEDIUM,
            endpoint="/api/v1/users",
            method="GET",
            evidence="Header absent",
            remediation="Add HSTS.",
        )
    )
    return result


# ── Health check ──────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"
        assert "service" in resp.json()


# ── Scan submission ────────────────────────────────────────────────────────────


class TestScanSubmission:
    def test_submit_returns_202(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/scans",
            json={"target_url": "http://localhost:8001"},
        )
        assert resp.status_code == 202

    def test_submit_returns_scan_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/scans",
            json={"target_url": "http://localhost:8001"},
        )
        data = resp.json()
        assert "scan_id" in data
        assert len(data["scan_id"]) > 0

    def test_submit_status_is_pending(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/scans",
            json={"target_url": "http://localhost:8001"},
        )
        assert resp.json()["status"] == "pending"

    def test_submit_stores_scan(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/scans",
            json={"target_url": "http://localhost:8001"},
        )
        scan_id = resp.json()["scan_id"]
        assert scan_id in scans_module._scans


# ── List scans ────────────────────────────────────────────────────────────────


class TestListScans:
    def test_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/scans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_submit(self, client: TestClient) -> None:
        client.post("/api/v1/scans", json={"target_url": "http://a.test"})
        client.post("/api/v1/scans", json={"target_url": "http://b.test"})
        resp = client.get("/api/v1/scans")
        assert len(resp.json()) == 2


# ── Get scan ──────────────────────────────────────────────────────────────────


class TestGetScan:
    def test_404_for_unknown_id(self, client: TestClient) -> None:
        resp = client.get("/api/v1/scans/does-not-exist")
        assert resp.status_code == 404

    def test_pending_scan_returns_status(self, client: TestClient) -> None:
        resp = client.post("/api/v1/scans", json={"target_url": "http://localhost:8001"})
        scan_id = resp.json()["scan_id"]
        detail = client.get(f"/api/v1/scans/{scan_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "pending"

    def test_complete_scan_returns_report(
        self, client: TestClient, completed_result: ScanResult
    ) -> None:
        scan_id = "test-complete-id"
        scans_module._scans[scan_id] = {
            "status": "complete",
            "target_url": "http://localhost:8001",
            "submitted_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:01:00+00:00",
            "result": completed_result,
            "error": None,
        }
        resp = client.get(f"/api/v1/scans/{scan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["finding_count"] == 1
        assert len(data["findings"]) == 1


# ── SARIF endpoint ────────────────────────────────────────────────────────────


class TestSarifEndpoint:
    def test_sarif_404_for_unknown(self, client: TestClient) -> None:
        resp = client.get("/api/v1/scans/bad-id/sarif")
        assert resp.status_code == 404

    def test_sarif_409_for_pending(self, client: TestClient) -> None:
        scan_id = "pending-id"
        scans_module._scans[scan_id] = {
            "status": "pending",
            "target_url": "http://t.test",
            "submitted_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "result": None,
            "error": None,
        }
        resp = client.get(f"/api/v1/scans/{scan_id}/sarif")
        assert resp.status_code == 409

    def test_sarif_complete_scan(self, client: TestClient, completed_result: ScanResult) -> None:
        scan_id = "sarif-complete-id"
        scans_module._scans[scan_id] = {
            "status": "complete",
            "target_url": "http://localhost:8001",
            "submitted_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:01:00+00:00",
            "result": completed_result,
            "error": None,
        }
        resp = client.get(f"/api/v1/scans/{scan_id}/sarif")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "2.1.0"
        assert len(data["runs"][0]["results"]) == 1


# ── Scanner orchestrator ──────────────────────────────────────────────────────


class TestRunScan:
    @pytest.mark.asyncio
    async def test_scan_returns_result(self) -> None:
        """run_scan returns a ScanResult with completed_at set."""
        # Patch every coroutine that would make real network calls
        with (
            patch(
                "src.scanner.fetch_openapi_spec",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "src.scanner._get_alice_token",
                new=AsyncMock(return_value="dummy_token"),
            ),
            patch("src.scanner.JWTTester") as MockJWT,
            patch("src.scanner.RateLimitTester") as MockRL,
            patch("src.scanner.BusinessFlowTester") as MockBF,
            patch("src.scanner.MisconfigTester") as MockMC,
            patch("src.scanner.InventoryTester") as MockINV,
            patch("src.scanner.ConsumptionTester") as MockCON,
            patch("src.scanner.FunctionAuthTester") as MockFA,
        ):
            for MockCls in (MockJWT, MockRL, MockBF, MockMC, MockINV, MockCON, MockFA):
                instance = MagicMock()
                instance.run = AsyncMock(return_value=None)
                MockCls.return_value = instance

            from src.scanner import run_scan  # noqa: PLC0415

            result = await run_scan("http://localhost:8001")

        assert result.completed_at is not None
        assert result.target_url == "http://localhost:8001"

    @pytest.mark.asyncio
    async def test_scan_no_token_skips_bola(self) -> None:
        """When login fails, BOLA and FunctionAuth testers are skipped."""
        with (
            patch(
                "src.scanner.fetch_openapi_spec",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "src.scanner._get_alice_token",
                new=AsyncMock(return_value=""),  # no token
            ),
            patch("src.scanner.JWTTester") as MockJWT,
            patch("src.scanner.RateLimitTester") as MockRL,
            patch("src.scanner.BusinessFlowTester") as MockBF,
            patch("src.scanner.MisconfigTester") as MockMC,
            patch("src.scanner.InventoryTester") as MockINV,
            patch("src.scanner.ConsumptionTester") as MockCON,
            patch("src.scanner.FunctionAuthTester") as MockFA,
            patch("src.scanner.BOLATester") as MockBOLA,
        ):
            for MockCls in (MockJWT, MockRL, MockBF, MockMC, MockINV, MockCON):
                instance = MagicMock()
                instance.run = AsyncMock(return_value=None)
                MockCls.return_value = instance

            from src.scanner import run_scan  # noqa: PLC0415

            await run_scan("http://localhost:8001")

            MockFA.assert_not_called()
            MockBOLA.assert_not_called()
