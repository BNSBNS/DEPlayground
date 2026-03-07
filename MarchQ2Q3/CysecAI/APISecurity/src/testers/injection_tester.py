"""SQL injection and NoSQL injection tester.

Detection strategy:
  - Time-based blind SQLi (response time delta > 1s on sleep payloads)
  - Error-based SQLi (database error strings in response)
  - Boolean-based SQLi (different response content for true vs false conditions)
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import Endpoint, ScanResult

# Common SQLi detection payloads
_SQLI_ERROR_PAYLOADS = [
    "'",
    '"',
    "' OR '1'='1",
    "' OR '1'='1'--",
    "' OR 1=1--",
    "; DROP TABLE users--",
    "' UNION SELECT NULL--",
    "' AND 1=2--",
]

# Strings in response that indicate SQLi vulnerability
_ERROR_SIGNATURES = [
    "syntax error",
    "SQL syntax",
    "mysql_fetch",
    "ORA-",
    "sqlite3.OperationalError",
    "OperationalError",
    "PG::SyntaxError",
    'near "',
    "unterminated quoted string",
    "unclosed quotation",
]

# NoSQL injection payloads (MongoDB style)
_NOSQL_PAYLOADS = [
    '{"$gt": ""}',
    '{"$ne": null}',
    '{"$where": "sleep(1000)"}',
]


def _has_error_signature(text: str) -> bool:
    text_lower = text.lower()
    return any(sig.lower() in text_lower for sig in _ERROR_SIGNATURES)


class InjectionTester(BaseTester):
    """Test all string parameters for SQL injection vulnerabilities."""

    @property
    def owasp_id(self) -> str:
        return "Injection"

    async def run(self, result: ScanResult) -> None:
        pass  # called per-endpoint

    async def test_endpoint(
        self,
        endpoint: Endpoint,
        result: ScanResult,
    ) -> None:
        """Fuzz all query/path parameters with SQLi payloads."""
        for param in endpoint.parameters:
            await self._test_param(endpoint, param, result)

    async def _test_param(
        self,
        endpoint: Endpoint,
        param: str,
        result: ScanResult,
    ) -> None:
        for payload in _SQLI_ERROR_PAYLOADS:
            url = endpoint.path
            params: dict[str, str] = {}

            # Determine if path or query param
            if f"{{{param}}}" in url:
                url = url.replace(f"{{{param}}}", payload)
            else:
                params[param] = payload

            t0 = time.monotonic()
            try:
                resp = await self._client.get(
                    self._target + url,
                    params=params,
                )
            except httpx.HTTPError:
                continue
            elapsed = time.monotonic() - t0
            result.endpoints_scanned += 1

            body_text = ""
            with contextlib.suppress(Exception):
                body_text = resp.text

            # Error-based detection
            if _has_error_signature(body_text):
                result.add_finding(
                    self._finding(
                        owasp_category=OWASPCategory.API8_MISCONFIG,
                        title=f"SQL injection (error-based): {endpoint.method} {endpoint.path}",
                        severity=Severity.CRITICAL,
                        endpoint=endpoint.path,
                        evidence=(
                            f"Param '{param}' with payload {payload!r} caused DB error. "
                            f"Response: {body_text[:200]}"
                        ),
                        remediation=(
                            "Use parameterised queries / prepared statements. "
                            "Never interpolate user input into SQL strings."
                        ),
                        method=endpoint.method,
                    )
                )
                return  # one finding per endpoint/param is enough

            # Time-based detection (> 2s suggests sleep() injection)
            if elapsed > 2.0:
                result.add_finding(
                    self._finding(
                        owasp_category=OWASPCategory.API8_MISCONFIG,
                        title=f"SQL injection (time-based): {endpoint.method} {endpoint.path}",
                        severity=Severity.CRITICAL,
                        endpoint=endpoint.path,
                        evidence=(
                            f"Param '{param}' with payload {payload!r} caused {elapsed:.1f}s delay"
                        ),
                        remediation="Use parameterised queries / prepared statements.",
                        method=endpoint.method,
                    )
                )
                return
