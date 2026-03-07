"""Tests for BOLA, Auth, and Function-Level Auth testers against the vulnerable app."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.models import Endpoint, OWASPCategory, ScanResult, Severity
from src.testers.auth_tester import (
    AuthTester,
    FunctionAuthTester,
    PropertyAuthTester,
    _forge_none_token,
)
from src.testers.bola_tester import BOLATester

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def scan_result() -> ScanResult:
    return ScanResult(target_url="http://localhost:8001")


@pytest.fixture()
def mock_client() -> httpx.AsyncClient:
    return MagicMock(spec=httpx.AsyncClient)


# ── _forge_none_token ────────────────────────────────────────────────────────


class TestForgeNoneToken:
    def test_has_three_parts(self) -> None:
        token = _forge_none_token({"user_id": 1, "role": "admin"})
        parts = token.split(".")
        assert len(parts) == 3

    def test_empty_signature(self) -> None:
        token = _forge_none_token({"user_id": 1})
        assert token.endswith(".")

    def test_header_alg_is_none(self) -> None:
        import base64  # noqa: PLC0415
        import json  # noqa: PLC0415

        token = _forge_none_token({"user_id": 99})
        header_part = token.split(".")[0]
        header = json.loads(base64.urlsafe_b64decode(header_part + "=="))
        assert header["alg"] == "none"

    def test_payload_preserved(self) -> None:
        import base64  # noqa: PLC0415
        import json  # noqa: PLC0415

        token = _forge_none_token({"user_id": 42, "role": "superadmin"})
        payload_part = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(payload_part + "=="))
        assert payload["user_id"] == 42
        assert payload["role"] == "superadmin"


# ── BOLATester (against live TestClient) ─────────────────────────────────────


class TestBOLATester:
    @pytest.fixture()
    def setup(self, alice_token: str) -> tuple:  # type: ignore[type-arg]
        # Use real httpx.AsyncClient wrapping the TestClient's transport
        from fastapi.testclient import TestClient  # noqa: PLC0415

        from src.vulnerable_app.main import app  # noqa: PLC0415

        tc = TestClient(app)

        async_client = MagicMock(spec=httpx.AsyncClient)

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            path = url.replace("http://localhost:8001", "")
            headers = dict(kwargs.get("headers", {}) or {})  # type: ignore[arg-type]
            resp_data = tc.get(path, headers=headers)
            mock_resp = MagicMock()
            mock_resp.status_code = resp_data.status_code
            mock_resp.json.return_value = resp_data.json()
            return mock_resp

        async_client.get = AsyncMock(side_effect=mock_get)
        return async_client, alice_token

    @pytest.mark.asyncio
    async def test_bola_detected_on_user_endpoint(
        self,
        setup: tuple,
        scan_result: ScanResult,  # type: ignore[type-arg]
    ) -> None:
        async_client, alice_token = setup
        tester = BOLATester(
            async_client,
            "http://localhost:8001",
            user_a_token=alice_token,
            user_b_ids=[2, 3, 4],
        )
        endpoint = Endpoint(path="/api/v1/users/{user_id}", method="GET", requires_auth=True)
        await tester.test_endpoint(endpoint, scan_result)
        # Should find BOLA (all IDs return 200 without auth check)
        assert scan_result.finding_count > 0
        finding = scan_result.findings[0]
        assert finding.owasp_category == OWASPCategory.API1_BOLA
        assert finding.severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_no_finding_on_404(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = BOLATester(
            mock_client,
            "http://localhost:8001",
            user_a_token="tok",
            user_b_ids=[999],
        )
        endpoint = Endpoint(path="/api/v1/users/{user_id}", method="GET", requires_auth=True)
        await tester.test_endpoint(endpoint, scan_result)
        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_http_error_skipped(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = BOLATester(
            mock_client,
            "http://localhost:8001",
            user_a_token="tok",
            user_b_ids=[1],
        )
        endpoint = Endpoint(path="/api/v1/users/{user_id}", method="GET")
        await tester.test_endpoint(endpoint, scan_result)
        assert scan_result.finding_count == 0


# ── AuthTester ────────────────────────────────────────────────────────────────


class TestAuthTester:
    @pytest.mark.asyncio
    async def test_no_token_finding_when_200(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = AuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/admin/users", method="GET", requires_auth=True)
        await tester.test_endpoint(endpoint, scan_result)
        findings = [
            f
            for f in scan_result.findings
            if "no token" in f.title.lower() or "Auth bypass" in f.title
        ]
        assert len(findings) > 0
        assert findings[0].severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_no_finding_when_401(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = AuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/profile", method="GET", requires_auth=True)
        await tester.test_endpoint(endpoint, scan_result)
        # 401 means auth is working
        auth_bypass = [f for f in scan_result.findings if "Auth bypass" in f.title]
        assert len(auth_bypass) == 0

    @pytest.mark.asyncio
    async def test_skips_unauthenticated_endpoints(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock()

        tester = AuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/search", method="GET", requires_auth=False)
        await tester.test_endpoint(endpoint, scan_result)
        mock_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_handled(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = AuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/profile", method="GET", requires_auth=True)
        await tester.test_endpoint(endpoint, scan_result)
        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_none_algorithm_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        bad_resp = MagicMock()
        bad_resp.status_code = 401
        # none algorithm test returns 200, others return 401
        mock_client.request = AsyncMock(side_effect=[bad_resp, bad_resp, ok_resp])

        tester = AuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/profile", method="GET", requires_auth=True)
        await tester.test_endpoint(endpoint, scan_result)
        none_findings = [f for f in scan_result.findings if "none" in f.title.lower()]
        assert len(none_findings) > 0
        assert none_findings[0].severity == Severity.CRITICAL
        assert none_findings[0].owasp_category == OWASPCategory.API2_AUTH


# ── PropertyAuthTester ────────────────────────────────────────────────────────


class TestPropertyAuthTester:
    @pytest.mark.asyncio
    async def test_mass_assignment_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"role": "admin", "username": "test_mass"}
        mock_client.post = AsyncMock(return_value=mock_resp)

        tester = PropertyAuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/auth/register", method="POST")
        await tester.test_endpoint(endpoint, scan_result)
        findings = [f for f in scan_result.findings if "Mass assignment" in f.title]
        assert len(findings) > 0

    @pytest.mark.asyncio
    async def test_skips_get_endpoints(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock()

        tester = PropertyAuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET")
        await tester.test_endpoint(endpoint, scan_result)
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_finding_when_role_not_reflected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"role": "user", "username": "test"}
        mock_client.post = AsyncMock(return_value=mock_resp)

        tester = PropertyAuthTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/auth/register", method="POST")
        await tester.test_endpoint(endpoint, scan_result)
        mass_assign = [f for f in scan_result.findings if "Mass assignment" in f.title]
        assert len(mass_assign) == 0


# ── FunctionAuthTester ────────────────────────────────────────────────────────


class TestFunctionAuthTester:
    @pytest.mark.asyncio
    async def test_finding_when_admin_accessible(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = FunctionAuthTester(
            mock_client,
            "http://localhost:8001",
            user_token="user_token_here",
            admin_paths=["/api/v1/admin/users"],
        )
        await tester.run(scan_result)
        assert scan_result.finding_count == 1
        assert scan_result.findings[0].owasp_category == OWASPCategory.API5_FUNCTION_AUTH
        assert scan_result.findings[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_no_finding_when_403(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = FunctionAuthTester(
            mock_client,
            "http://localhost:8001",
            user_token="tok",
            admin_paths=["/api/v1/admin/users"],
        )
        await tester.run(scan_result)
        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_http_error_skipped(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = FunctionAuthTester(
            mock_client, "http://localhost:8001", user_token="tok", admin_paths=["/admin"]
        )
        await tester.run(scan_result)
        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_multiple_admin_paths(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        ok = MagicMock()
        ok.status_code = 200
        forbidden = MagicMock()
        forbidden.status_code = 403
        mock_client.get = AsyncMock(side_effect=[ok, forbidden, ok])

        tester = FunctionAuthTester(
            mock_client,
            "http://localhost:8001",
            user_token="tok",
            admin_paths=["/admin", "/management", "/internal"],
        )
        await tester.run(scan_result)
        assert scan_result.finding_count == 2
