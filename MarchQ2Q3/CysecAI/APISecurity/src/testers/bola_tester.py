"""API1:2023 — Broken Object Level Authorization (BOLA/IDOR) tester."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import Endpoint, ScanResult


class BOLATester(BaseTester):
    """Detect BOLA by authenticating as user A and accessing user B's resources."""

    @property
    def owasp_id(self) -> str:
        return "API1:2023"

    def __init__(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        *,
        user_a_token: str,
        user_b_ids: list[str | int],
    ) -> None:
        super().__init__(client, target_url)
        self._token_a = user_a_token
        self._b_ids = user_b_ids

    async def run(self, result: ScanResult) -> None:
        """Test all parameterised endpoints for BOLA."""
        pass  # Requires endpoint map — called via test_endpoint()

    async def test_endpoint(
        self,
        endpoint: Endpoint,
        result: ScanResult,
    ) -> None:
        """Test a single parameterised endpoint for BOLA."""
        from src.discovery.endpoint_mapper import generate_test_urls  # noqa: PLC0415

        headers = {"Authorization": f"Bearer {self._token_a}"}
        for other_id in self._b_ids:
            urls = generate_test_urls(endpoint, [other_id])
            for url in urls:
                try:
                    resp = await self._client.get(self._target + url, headers=headers)
                except httpx.HTTPError:
                    continue
                if resp.status_code == 200:
                    result.add_finding(
                        self._finding(
                            owasp_category=OWASPCategory.API1_BOLA,
                            title=f"BOLA: {endpoint.method} {endpoint.path}",
                            severity=Severity.HIGH,
                            endpoint=url,
                            evidence=(
                                f"User A accessed resource {url} (belongs to another user). "
                                f"HTTP {resp.status_code}"
                            ),
                            remediation=(
                                "Verify that the authenticated user owns the requested resource "
                                "before returning data. Use server-side ownership checks."
                            ),
                            method=endpoint.method,
                        )
                    )
                result.endpoints_scanned += 1
