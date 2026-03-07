"""API8:2023 — Security Misconfiguration tester.

Checks:
  - CORS wildcard (Access-Control-Allow-Origin: *)
  - Missing security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
  - Verbose error responses (stack traces in 5xx bodies)
  - Exposed debug / internal management endpoints
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import ScanResult

_SECURITY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": (
        "Missing HSTS — connections vulnerable to protocol downgrade attacks"
    ),
    "Content-Security-Policy": "Missing CSP — XSS attacks can load arbitrary scripts",
    "X-Frame-Options": "Missing X-Frame-Options — clickjacking attacks possible",
    "X-Content-Type-Options": ("Missing X-Content-Type-Options — MIME sniffing attacks possible"),
}

# Patterns in 5xx bodies that indicate verbose error leakage
_STACKTRACE_SIGNATURES = [
    "traceback",
    'file "',
    "traceback (most recent call last)",
    "exception:",
    "at line",
    "stack trace",
]

# Common debug / internal endpoints that should not be exposed in production
_DEBUG_PATHS = [
    "/api/v1/debug/status",
    "/api/v1/debug",
    "/debug",
    "/api/debug",
    "/actuator",
    "/api/v1/metrics",
    "/metrics",
    "/api/v1/internal",
    "/internal",
]


def _has_stacktrace(text: str) -> bool:
    """Return True if the response body contains stack-trace indicators."""
    text_lower = text.lower()
    return any(sig in text_lower for sig in _STACKTRACE_SIGNATURES)


class MisconfigTester(BaseTester):
    """Test for API security misconfigurations (API8:2023)."""

    @property
    def owasp_id(self) -> str:
        return "API8:2023"

    async def run(self, result: ScanResult) -> None:
        await self._test_cors(result)
        await self._test_security_headers(result)
        await self._test_verbose_errors(result)
        await self._test_debug_endpoints(result)

    async def _test_cors(self, result: ScanResult) -> None:
        """Check if CORS wildcard allows arbitrary origins."""
        try:
            resp = await self._client.options(
                self._target + "/api/v1/users",
                headers={
                    "Origin": "https://evil.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        acao = resp.headers.get("access-control-allow-origin", "")
        if acao in ("*", "https://evil.example.com"):
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API8_MISCONFIG,
                    title="CORS wildcard allows any origin",
                    severity=Severity.HIGH,
                    endpoint="/api/v1/users",
                    evidence=f"Access-Control-Allow-Origin: {acao}",
                    remediation=(
                        "Restrict CORS to known origins. Never use '*' for authenticated APIs. "
                        "Maintain an explicit allowlist of trusted origins."
                    ),
                    method="OPTIONS",
                )
            )

    async def _test_security_headers(self, result: ScanResult) -> None:
        """Check for missing mandatory security response headers."""
        try:
            resp = await self._client.get(self._target + "/api/v1/users/1")
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        present = {k.lower() for k in resp.headers}
        for header, description in _SECURITY_HEADERS.items():
            if header.lower() not in present:
                result.add_finding(
                    self._finding(
                        owasp_category=OWASPCategory.API8_MISCONFIG,
                        title=f"Missing security header: {header}",
                        severity=Severity.MEDIUM,
                        endpoint="/api/v1/users/1",
                        evidence=description,
                        remediation=f"Add '{header}' header to all API responses.",
                        method="GET",
                    )
                )

    async def _test_verbose_errors(self, result: ScanResult) -> None:
        """Check if server returns stack traces in error responses."""
        try:
            resp = await self._client.get(self._target + "/api/v1/debug/status")
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        body_text = ""
        with contextlib.suppress(Exception):
            body_text = resp.text
        if resp.status_code >= 500 and _has_stacktrace(body_text):
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API8_MISCONFIG,
                    title="Verbose error — stack trace in response",
                    severity=Severity.MEDIUM,
                    endpoint="/api/v1/debug/status",
                    evidence=f"HTTP {resp.status_code} response contains: {body_text[:200]}",
                    remediation=(
                        "Return generic error messages to clients. Log full stack traces "
                        "server-side only. Disable debug mode in production."
                    ),
                    method="GET",
                )
            )

    async def _test_debug_endpoints(self, result: ScanResult) -> None:
        """Check for exposed debug or internal management endpoints."""
        for path in _DEBUG_PATHS:
            try:
                resp = await self._client.get(self._target + path)
            except httpx.HTTPError:
                continue
            result.endpoints_scanned += 1
            # 200 = accessible, 500 = exists but errored — both indicate exposure
            if resp.status_code in (200, 500):
                result.add_finding(
                    self._finding(
                        owasp_category=OWASPCategory.API8_MISCONFIG,
                        title=f"Debug endpoint exposed: GET {path}",
                        severity=Severity.MEDIUM,
                        endpoint=path,
                        evidence=f"GET {path} returned HTTP {resp.status_code}",
                        remediation=(
                            "Remove debug and internal endpoints from production builds. "
                            "If required, protect with authentication and IP allowlisting."
                        ),
                        method="GET",
                    )
                )
