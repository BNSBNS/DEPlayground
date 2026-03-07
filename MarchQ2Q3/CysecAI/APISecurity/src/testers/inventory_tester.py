"""API9:2023 — Improper Inventory Management tester.

Detects:
  - Shadow / legacy API versions still active alongside the current version
  - Undocumented common endpoints (GraphQL, Swagger, internal routes)
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import Endpoint, ScanResult

# Common paths that reveal undocumented / shadow API surfaces
_SHADOW_PATHS = [
    "/graphql",
    "/api/graphql",
    "/swagger",
    "/swagger-ui.html",
    "/swagger-ui",
    "/api-docs",
    "/api/swagger",
    "/api/v0",
    "/api/v2",
    "/api/internal",
    "/private",
    "/internal",
    "/admin",
    "/api/admin",
]

# Matches /v<N>/ version segments in API paths
_VERSION_RE = re.compile(r"/v(\d+)/")


def _legacy_paths(path: str) -> list[str]:
    """Return older-version and prefix-stripped variants of a documented path."""
    match = _VERSION_RE.search(path)
    if not match:
        return []
    version = int(match.group(1))
    results: list[str] = []
    for v in range(max(0, version - 2), version):
        results.append(_VERSION_RE.sub(f"/v{v}/", path, count=1))
    # Also try without /api/ prefix (e.g., /api/v1/users → /v1/users)
    if "/api/" in path:
        results.append(path.replace("/api/", "/", 1))
    return results


class InventoryTester(BaseTester):
    """Detect shadow and undocumented API endpoints (API9:2023)."""

    @property
    def owasp_id(self) -> str:
        return "API9:2023"

    async def run(self, result: ScanResult) -> None:
        """Probe common shadow paths."""
        for path in _SHADOW_PATHS:
            await self._probe(path, "Shadow", result)

    async def test_endpoint(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Check if legacy versions of this documented endpoint still exist."""
        for legacy_path in _legacy_paths(endpoint.path):
            await self._probe(legacy_path, "Legacy", result)

    async def _probe(self, path: str, kind: str, result: ScanResult) -> None:
        try:
            resp = await self._client.get(self._target + path)
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code in (404, 405):
            return
        body_text = ""
        with contextlib.suppress(Exception):
            body_text = resp.text
        result.add_finding(
            self._finding(
                owasp_category=OWASPCategory.API9_INVENTORY,
                title=f"{kind} API endpoint active: GET {path}",
                severity=Severity.MEDIUM,
                endpoint=path,
                evidence=(
                    f"GET {path} returned HTTP {resp.status_code}. "
                    f"Content preview: {body_text[:100]}"
                ),
                remediation=(
                    "Maintain an up-to-date API inventory. Decommission legacy versions. "
                    "Block or redirect old API paths to the current version."
                ),
                method="GET",
            )
        )
