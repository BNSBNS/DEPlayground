"""Tests for Phase 5 testers: RateLimit, BusinessFlow, SSRF, Misconfig."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.models import Endpoint, OWASPCategory, ScanResult, Severity
from src.testers.business_flow_tester import BusinessFlowTester
from src.testers.misconfig_tester import MisconfigTester, _has_stacktrace
from src.testers.rate_limit_tester import RateLimitTester
from src.testers.ssrf_tester import SSRFTester, _is_url_param


@pytest.fixture()
def scan_result() -> ScanResult:
    return ScanResult(target_url="http://localhost:8001")


# ── Rate Limit Tester ─────────────────────────────────────────────────────────


class TestRateLimitTester:
    @pytest.mark.asyncio
    async def test_no_rate_limit_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = RateLimitTester(mock_client, "http://localhost:8001", burst_count=5)
        endpoint = Endpoint(path="/api/v1/auth/login", method="POST")
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 1
        finding = scan_result.findings[0]
        assert finding.severity == Severity.HIGH
        assert "No rate limiting" in finding.title
        assert finding.owasp_category == OWASPCategory.API4_CONSUMPTION

    @pytest.mark.asyncio
    async def test_rate_limited_429_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = RateLimitTester(mock_client, "http://localhost:8001", burst_count=5)
        endpoint = Endpoint(path="/api/v1/auth/login", method="POST")
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_rate_limited_503_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = RateLimitTester(mock_client, "http://localhost:8001", burst_count=5)
        endpoint = Endpoint(path="/api/v1/auth/login", method="POST")
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_http_error_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = RateLimitTester(mock_client, "http://localhost:8001", burst_count=5)
        endpoint = Endpoint(path="/api/v1/auth/login", method="POST")
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_run_probes_default_endpoints(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = RateLimitTester(mock_client, "http://localhost:8001", burst_count=3)
        await tester.run(scan_result)

        # Default probe = 2 paths, each unthrottled → 2 findings
        assert scan_result.finding_count == 2

    @pytest.mark.asyncio
    async def test_endpoints_scanned_incremented(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.request = AsyncMock(return_value=mock_resp)

        tester = RateLimitTester(mock_client, "http://localhost:8001", burst_count=10)
        endpoint = Endpoint(path="/api/v1/auth/login", method="POST")
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.endpoints_scanned == 10


# ── Business Flow Tester ──────────────────────────────────────────────────────


class TestBusinessFlowTester:
    @pytest.mark.asyncio
    async def test_mass_registration_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_client.post = AsyncMock(return_value=mock_resp)

        tester = BusinessFlowTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 1
        finding = scan_result.findings[0]
        assert "mass account registration" in finding.title.lower()
        assert finding.owasp_category == OWASPCategory.API6_BUSINESS_FLOW
        assert finding.severity == Severity.HIGH
        assert finding.method == "POST"

    @pytest.mark.asyncio
    async def test_rate_limited_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_client.post = AsyncMock(return_value=mock_resp)

        tester = BusinessFlowTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_connection_error_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = BusinessFlowTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_partial_success_below_threshold_no_finding(
        self, scan_result: ScanResult
    ) -> None:
        """50% success rate is below the 80% threshold — no finding."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        # Alternate 201 and 429 for 20 total responses (10 needed)
        responses = [MagicMock(status_code=201), MagicMock(status_code=429)] * 10
        mock_client.post = AsyncMock(side_effect=responses)

        tester = BusinessFlowTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_endpoint_registered_correctly(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_client.post = AsyncMock(return_value=mock_resp)

        tester = BusinessFlowTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.endpoints_scanned == 10  # _REGISTRATION_COUNT


# ── SSRF Tester helpers ───────────────────────────────────────────────────────


class TestIsUrlParam:
    def test_url_param(self) -> None:
        assert _is_url_param("url") is True

    def test_callback_url_param(self) -> None:
        assert _is_url_param("callback_url") is True

    def test_redirect_param(self) -> None:
        assert _is_url_param("redirect") is True

    def test_webhook_param(self) -> None:
        assert _is_url_param("webhook") is True

    def test_proxy_param(self) -> None:
        assert _is_url_param("proxy") is True

    def test_non_url_param_username(self) -> None:
        assert _is_url_param("username") is False

    def test_non_url_param_user_id(self) -> None:
        assert _is_url_param("user_id") is False

    def test_case_insensitive(self) -> None:
        assert _is_url_param("CallbackURL") is True

    def test_dest_param(self) -> None:
        assert _is_url_param("dest") is True


# ── SSRF Tester ───────────────────────────────────────────────────────────────


class TestSSRFTester:
    @pytest.mark.asyncio
    async def test_no_url_params_skips_requests(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()

        tester = SSRFTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/users", method="GET", parameters=["limit", "offset"])
        await tester.test_endpoint(endpoint, scan_result)

        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_ssrf_not_detected_on_400(self, scan_result: ScanResult) -> None:
        """Server rejects the payload — not vulnerable."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = SSRFTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/fetch", method="GET", parameters=["url"])
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_ssrf_detected_on_large_200_response(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "a" * 200  # > 50 bytes — suspicious content
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = SSRFTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/fetch", method="GET", parameters=["url"])
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 1
        assert scan_result.findings[0].owasp_category == OWASPCategory.API7_SSRF
        assert scan_result.findings[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_ssrf_not_detected_on_small_200(self, scan_result: ScanResult) -> None:
        """200 with tiny body is not flagged (e.g., '{}' echo)."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"  # < 50 bytes
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = SSRFTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/fetch", method="GET", parameters=["url"])
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_path_param_skipped(self, scan_result: ScanResult) -> None:
        """URL-like path params are skipped — SSRF only relevant for query params."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()

        tester = SSRFTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/proxy/{url}", method="GET", parameters=["url"])
        await tester.test_endpoint(endpoint, scan_result)

        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_http_error_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = SSRFTester(mock_client, "http://localhost:8001")
        endpoint = Endpoint(path="/api/v1/fetch", method="GET", parameters=["url"])
        await tester.test_endpoint(endpoint, scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_run_is_noop(self, scan_result: ScanResult) -> None:
        """run() is a no-op — testers are per-endpoint."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        tester = SSRFTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)
        assert scan_result.finding_count == 0


# ── Misconfig Tester helpers ──────────────────────────────────────────────────


class TestHasStacktrace:
    def test_detects_traceback_keyword(self) -> None:
        assert _has_stacktrace("Traceback (most recent call last):") is True

    def test_detects_file_keyword(self) -> None:
        assert _has_stacktrace('File "app.py", line 10') is True

    def test_detects_exception_keyword(self) -> None:
        assert _has_stacktrace("Exception: division by zero") is True

    def test_clean_message_no_match(self) -> None:
        assert _has_stacktrace('{"error": "Not found"}') is False

    def test_empty_string(self) -> None:
        assert _has_stacktrace("") is False

    def test_case_insensitive(self) -> None:
        assert _has_stacktrace("TRACEBACK (most recent call last):") is True


# ── Misconfig Tester ──────────────────────────────────────────────────────────


class TestMisconfigTester:
    @pytest.mark.asyncio
    async def test_cors_wildcard_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        cors_resp = MagicMock()
        cors_resp.status_code = 200
        cors_resp.headers = {"access-control-allow-origin": "*"}
        mock_client.options = AsyncMock(return_value=cors_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_cors(scan_result)

        assert scan_result.finding_count == 1
        assert "CORS" in scan_result.findings[0].title
        assert scan_result.findings[0].severity == Severity.HIGH
        assert scan_result.findings[0].owasp_category == OWASPCategory.API8_MISCONFIG

    @pytest.mark.asyncio
    async def test_cors_arbitrary_origin_reflected(self, scan_result: ScanResult) -> None:
        """Server reflects the attacker origin — equally dangerous."""
        mock_client = MagicMock(spec=httpx.AsyncClient)
        cors_resp = MagicMock()
        cors_resp.status_code = 200
        cors_resp.headers = {"access-control-allow-origin": "https://evil.example.com"}
        mock_client.options = AsyncMock(return_value=cors_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_cors(scan_result)

        assert scan_result.finding_count == 1

    @pytest.mark.asyncio
    async def test_cors_restricted_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        cors_resp = MagicMock()
        cors_resp.status_code = 200
        cors_resp.headers = {"access-control-allow-origin": "https://trusted.example.com"}
        mock_client.options = AsyncMock(return_value=cors_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_cors(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_cors_http_error_no_crash(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.options = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_cors(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_all_security_headers_missing(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}  # no security headers at all
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_security_headers(scan_result)

        assert scan_result.finding_count == 4
        assert all(f.severity == Severity.MEDIUM for f in scan_result.findings)

    @pytest.mark.asyncio
    async def test_headers_present_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            "strict-transport-security": "max-age=31536000",
            "content-security-policy": "default-src 'self'",
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
        }
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_security_headers(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_verbose_error_stack_trace_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = 'Traceback (most recent call last):\n  File "app.py", line 42'
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_verbose_errors(scan_result)

        assert scan_result.finding_count == 1
        assert "stack trace" in scan_result.findings[0].title.lower()
        assert scan_result.findings[0].severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_clean_500_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = '{"error": "Internal server error"}'
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_verbose_errors(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_debug_endpoint_500_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 500  # exists but crashes — still exposed
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_debug_endpoints(scan_result)

        debug_findings = [f for f in scan_result.findings if "Debug endpoint" in f.title]
        assert len(debug_findings) > 0
        assert debug_findings[0].owasp_category == OWASPCategory.API8_MISCONFIG

    @pytest.mark.asyncio
    async def test_debug_endpoint_200_detected(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_debug_endpoints(scan_result)

        assert scan_result.finding_count > 0

    @pytest.mark.asyncio
    async def test_debug_endpoint_404_no_finding(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_resp)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester._test_debug_endpoints(scan_result)

        assert scan_result.finding_count == 0

    @pytest.mark.asyncio
    async def test_full_run_multiple_findings(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        cors_resp = MagicMock(
            status_code=200,
            headers={"access-control-allow-origin": "*"},
        )
        no_headers_resp = MagicMock(status_code=200, headers={}, text="ok")
        verbose_resp = MagicMock(
            status_code=500,
            text='Traceback (most recent call last):\n  File "app.py"',
        )
        not_found = MagicMock(status_code=404)
        mock_client.options = AsyncMock(return_value=cors_resp)
        # Calls: security headers, verbose errors, then N debug paths
        mock_client.get = AsyncMock(side_effect=[no_headers_resp, verbose_resp] + [not_found] * 20)

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        # CORS(1) + 4 missing headers + 1 verbose error = 6 minimum
        assert scan_result.finding_count >= 6

    @pytest.mark.asyncio
    async def test_full_run_all_http_errors(self, scan_result: ScanResult) -> None:
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.options = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        tester = MisconfigTester(mock_client, "http://localhost:8001")
        await tester.run(scan_result)

        assert scan_result.finding_count == 0
