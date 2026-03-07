"""Tests for Injection and JWT testers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.models import Endpoint, OWASPCategory, ScanResult, Severity
from src.testers.injection_tester import InjectionTester, _has_error_signature
from src.testers.jwt_tester import (
    JWTTester,
    forge_expired_token,
    forge_none_token,
    try_brute_force,
)


@pytest.fixture()
def scan_result() -> ScanResult:
    return ScanResult(target_url="http://localhost:8001")


# ── Injection helpers ─────────────────────────────────────────────────────────


class TestHasErrorSignature:
    def test_detects_sqlite_error(self) -> None:
        assert _has_error_signature("sqlite3.OperationalError: near 'x'") is True

    def test_detects_mysql_syntax(self) -> None:
        assert _has_error_signature("You have an error in your SQL syntax") is True

    def test_detects_ora_error(self) -> None:
        assert _has_error_signature("ORA-00942: table or view does not exist") is True

    def test_case_insensitive(self) -> None:
        assert _has_error_signature("SYNTAX ERROR near token") is True

    def test_no_match_on_clean_response(self) -> None:
        assert _has_error_signature('{"username": "alice"}') is False

    def test_empty_string(self) -> None:
        assert _has_error_signature("") is False


# ── InjectionTester ───────────────────────────────────────────────────────────


class TestInjectionTester:
    @pytest.mark.asyncio
    async def test_error_based_sqli_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = 'sqlite3.OperationalError: near "\'": syntax error'
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InjectionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/search", method="GET", parameters=["q"])
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count > 0
        assert scan_result.findings[0].severity == Severity.CRITICAL
        assert "SQL injection" in scan_result.findings[0].title

    @pytest.mark.asyncio
    async def test_clean_response_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"users": []}'
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InjectionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/search", method="GET", parameters=["q"])
        await tester.test_endpoint(endpoint, scan_result)
        # No DB error signatures → no finding
        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_http_error_skipped(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = InjectionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/search", method="GET", parameters=["q"])
        await tester.test_endpoint(endpoint, scan_result)
        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_no_params_skips_test(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()

        tester = InjectionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET", parameters=[])
        await tester.test_endpoint(endpoint, scan_result)
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_path_param_substituted(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = InjectionTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users/{user_id}", method="GET", parameters=["user_id"])
        await tester.test_endpoint(endpoint, scan_result)
        # Verify get was called (path param substituted, not query param)
        assert mock_client.get.call_count > 0


# ── JWT helpers ────────────────────────────────────────────────────────────────


class TestForgeNoneToken:
    def test_valid_structure(self) -> None:
        token = forge_none_token({"user_id": 1})
        assert token.count(".") == 2
        assert token.endswith(".")

    def test_alg_is_none(self) -> None:
        import base64  # noqa: PLC0415
        import json  # noqa: PLC0415

        token = forge_none_token({"user_id": 99})
        header = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))
        assert header["alg"] == "none"


class TestTryBruteForce:
    def test_finds_weak_secret(self) -> None:
        import jwt  # noqa: PLC0415

        token = jwt.encode({"user_id": 1}, "secret123", algorithm="HS256")
        result = try_brute_force(token)
        assert result == "secret123"

    def test_returns_none_for_strong_secret(self) -> None:
        import jwt  # noqa: PLC0415

        token = jwt.encode({"user_id": 1}, "VERY_STRONG_RANDOM_SECRET_XYZ_99!", algorithm="HS256")
        result = try_brute_force(token)
        assert result is None

    def test_returns_none_for_malformed_token(self) -> None:
        result = try_brute_force("not.a.jwt")
        assert result is None


class TestForgeExpiredToken:
    def test_creates_token(self) -> None:
        token = forge_expired_token("secret123", {"user_id": 1})
        assert token != ""
        assert "." in token

    def test_token_is_expired(self) -> None:
        import jwt  # noqa: PLC0415

        token = forge_expired_token("secret123", {"user_id": 1})
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, "secret123", algorithms=["HS256"])


# ── JWTTester ─────────────────────────────────────────────────────────────────


class TestJWTTester:
    @pytest.mark.asyncio
    async def test_none_algorithm_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"access_token": "dummy"}
        none_resp = MagicMock()
        none_resp.status_code = 200
        mock_client.post = AsyncMock(return_value=ok_resp)
        mock_client.get = AsyncMock(return_value=none_resp)

        tester = JWTTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        none_findings = [f for f in scan_result.findings if "none" in f.title.lower()]
        assert len(none_findings) > 0
        assert none_findings[0].severity == Severity.CRITICAL
        assert none_findings[0].owasp_category == OWASPCategory.API2_AUTH

    @pytest.mark.asyncio
    async def test_weak_secret_detected(self, scan_result: ScanResult) -> None:
        import jwt  # noqa: PLC0415

        real_token = jwt.encode({"user_id": 1, "role": "user"}, "secret123", algorithm="HS256")
        mock_client = MagicMock(spec=httpx.AsyncClient)
        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {"access_token": real_token}
        # none algorithm test returns 401
        not_ok = MagicMock()
        not_ok.status_code = 401
        mock_client.post = AsyncMock(return_value=login_resp)
        mock_client.get = AsyncMock(return_value=not_ok)

        tester = JWTTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        brute_findings = [f for f in scan_result.findings if "Weak JWT" in f.title]
        assert len(brute_findings) > 0
        assert "secret123" in brute_findings[0].evidence

    @pytest.mark.asyncio
    async def test_no_finding_when_none_rejected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        login_resp = MagicMock()
        login_resp.status_code = 401  # login fails
        mock_client.post = AsyncMock(return_value=login_resp)
        reject_resp = MagicMock()
        reject_resp.status_code = 401
        mock_client.get = AsyncMock(return_value=reject_resp)

        tester = JWTTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)
        none_findings = [f for f in scan_result.findings if "none" in f.title.lower()]
        assert len(none_findings) == 0

    @pytest.mark.asyncio
    async def test_http_error_handled(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = JWTTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)
        assert scan_result.finding_count == 0
