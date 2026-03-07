"""API7:2023 — Server-Side Request Forgery tester.

Strategy:
  - Identify URL-like query parameters (url, callback, redirect, webhook, etc.)
  - Inject common internal SSRF payloads (cloud metadata, loopback, Redis, ES)
  - Flag if:
      • Server returns HTTP 200 with substantial content (may have fetched the URL)
      • Response takes > _SSRF_DELAY_THRESHOLD seconds (TCP connect attempt)
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

# Internal / cloud metadata endpoints commonly used in SSRF attacks
_SSRF_PAYLOADS = [
    "http://169.254.169.254/latest/meta-data/",  # AWS EC2 metadata
    "http://metadata.google.internal/computeMetadata/v1/",  # GCP metadata
    "http://169.254.170.2/v2/credentials/",  # ECS task metadata
    "http://localhost:22",  # SSH
    "http://127.0.0.1:6379",  # Redis
    "http://127.0.0.1:9200",  # Elasticsearch
    "http://[::1]:80",  # IPv6 loopback
    "file:///etc/passwd",  # Local file inclusion
]

# Parameter name patterns that indicate URL-type inputs
_URL_PARAM_PATTERNS = [
    "url",
    "callback",
    "redirect",
    "webhook",
    "endpoint",
    "target",
    "src",
    "href",
    "link",
    "next",
    "return",
    "dest",
    "uri",
    "fetch",
    "proxy",
]

_SSRF_DELAY_THRESHOLD = 2.0  # seconds — suggests server attempted TCP connect
_SSRF_CONTENT_MIN_LEN = 50  # bytes — suspicious if 200 returned with real content


def _is_url_param(name: str) -> bool:
    """Return True if the parameter name suggests it accepts a URL."""
    name_lower = name.lower()
    return any(pat in name_lower for pat in _URL_PARAM_PATTERNS)


class SSRFTester(BaseTester):
    """Detect SSRF-vulnerable URL parameters (API7:2023)."""

    @property
    def owasp_id(self) -> str:
        return "API7:2023"

    async def run(self, result: ScanResult) -> None:
        pass  # called per-endpoint

    async def test_endpoint(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Test all URL-like query parameters for SSRF."""
        url_params = [p for p in endpoint.parameters if _is_url_param(p)]
        for param in url_params:
            await self._test_param(endpoint, param, result)

    async def _test_param(self, endpoint: Endpoint, param: str, result: ScanResult) -> None:
        # Skip path parameters — SSRF is a query/body concern
        if f"{{{param}}}" in endpoint.path:
            return

        for payload in _SSRF_PAYLOADS:
            t0 = time.monotonic()
            resp_status: int | None = None
            body_text = ""

            with contextlib.suppress(httpx.HTTPError):
                resp = await self._client.get(
                    self._target + endpoint.path,
                    params={param: payload},
                )
                resp_status = resp.status_code
                with contextlib.suppress(Exception):
                    body_text = resp.text

            elapsed = time.monotonic() - t0
            result.endpoints_scanned += 1

            if resp_status is None:
                continue

            # Time-based: server attempted TCP connect to internal host
            if elapsed >= _SSRF_DELAY_THRESHOLD:
                result.add_finding(
                    self._finding(
                        owasp_category=OWASPCategory.API7_SSRF,
                        title=f"Potential SSRF (time-based): {endpoint.method} {endpoint.path}",
                        severity=Severity.HIGH,
                        endpoint=endpoint.path,
                        evidence=(
                            f"Param '{param}' with payload {payload!r} caused "
                            f"{elapsed:.1f}s delay — server may have attempted TCP connect."
                        ),
                        remediation=(
                            "Validate and allowlist URLs before making outbound requests. "
                            "Block internal IP ranges and cloud metadata endpoints."
                        ),
                        method=endpoint.method,
                    )
                )
                return

            # Content-based: server returned 200 with substantial content
            if resp_status == 200 and len(body_text) > _SSRF_CONTENT_MIN_LEN:
                result.add_finding(
                    self._finding(
                        owasp_category=OWASPCategory.API7_SSRF,
                        title=(
                            f"Potential SSRF (response content): {endpoint.method} {endpoint.path}"
                        ),
                        severity=Severity.HIGH,
                        endpoint=endpoint.path,
                        evidence=(
                            f"Param '{param}' with SSRF payload {payload!r} returned "
                            f"HTTP 200 with {len(body_text)} bytes of content. "
                            "Server may have fetched the internal URL."
                        ),
                        remediation=(
                            "Validate and allowlist URLs before making outbound requests. "
                            "Block internal IP ranges and cloud metadata endpoints."
                        ),
                        method=endpoint.method,
                    )
                )
                return
