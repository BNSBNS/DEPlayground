"""API4:2023 — Unrestricted Resource Consumption (rate limiting) tester.

Strategy:
  - Fire _BURST_COUNT concurrent requests at the same endpoint
  - If zero responses are 429 / 503, the endpoint has no rate limiting
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import Endpoint, ScanResult

_BURST_COUNT = 50  # concurrent requests per probe
_RATE_LIMIT_CODES: frozenset[int] = frozenset({429, 503})

# Endpoints to probe in the standalone run()
_DEFAULT_PROBE_PATHS = [
    ("/api/v1/auth/login", "POST"),
    ("/api/v1/auth/register", "POST"),
]


class RateLimitTester(BaseTester):
    """Test endpoints for missing rate limiting (API4:2023)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        *,
        burst_count: int = _BURST_COUNT,
    ) -> None:
        super().__init__(client, target_url)
        self._burst_count = burst_count

    @property
    def owasp_id(self) -> str:
        return "API4:2023"

    async def run(self, result: ScanResult) -> None:
        """Probe default high-value endpoints for missing rate limiting."""
        for path, method in _DEFAULT_PROBE_PATHS:
            await self._burst_test(path, method, result)

    async def test_endpoint(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Burst-test a specific endpoint."""
        await self._burst_test(endpoint.path, endpoint.method, result)

    async def _burst_test(self, path: str, method: str, result: ScanResult) -> None:
        tasks = [self._single_request(path, method) for _ in range(self._burst_count)]
        gathered: list[int | None] = list(await asyncio.gather(*tasks))

        valid = [r for r in gathered if r is not None]
        result.endpoints_scanned += len(valid)
        if not valid:
            return

        limited = sum(1 for r in valid if r in _RATE_LIMIT_CODES)
        if limited == 0:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API4_CONSUMPTION,
                    title=f"No rate limiting: {method} {path}",
                    severity=Severity.HIGH,
                    endpoint=path,
                    evidence=(
                        f"Sent {len(valid)} concurrent requests — zero 429/503 responses. "
                        "Endpoint has no throttling."
                    ),
                    remediation=(
                        "Add rate limiting per IP and per user. Return HTTP 429 with "
                        "Retry-After header. Consider token bucket or sliding window algorithms."
                    ),
                    method=method,
                )
            )

    async def _single_request(self, path: str, method: str) -> int | None:
        with contextlib.suppress(httpx.HTTPError):
            resp = await self._client.request(
                method,
                self._target + path,
                json={"username": "probe", "password": "probe"},
            )
            return resp.status_code
        return None
