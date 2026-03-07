"""API10:2023 — Unsafe Consumption of APIs tester.

Detects:
  - List endpoints that return unbounded data (no pagination metadata)
  - API responses that expose sensitive field names in aggregated payloads
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import Endpoint, ScanResult

# Field names that indicate sensitive data leakage in aggregated responses
_SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "ssn",
        "credit_card",
        "card_number",
        "cvv",
        "pin",
        "private_key",
    }
)

# Fields present in well-paginated responses
_PAGINATION_KEYS = frozenset({"page", "limit", "total", "next", "previous", "offset", "cursor"})

# List endpoints to probe in standalone run()
_LIST_PROBE_PATHS = [
    "/api/v1/users",
    "/api/v1/admin/users",
    "/api/v1/search",
]

# Threshold: list responses with >= this many items and no pagination are flagged
_UNPAGINATED_THRESHOLD = 5


def _flatten_keys(obj: Any, prefix: str = "") -> set[str]:
    """Recursively collect all JSON key names from a nested structure."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys.add(full_key.lower())
            keys.add(k.lower())  # also index the leaf name for pattern matching
            keys |= _flatten_keys(v, full_key)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item, prefix)
    return keys


class ConsumptionTester(BaseTester):
    """Detect unsafe API consumption patterns (API10:2023)."""

    @property
    def owasp_id(self) -> str:
        return "API10:2023"

    async def run(self, result: ScanResult) -> None:
        """Probe default list endpoints for consumption vulnerabilities."""
        for path in _LIST_PROBE_PATHS:
            await self._test_path(path, result)

    async def test_endpoint(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Test a specific GET endpoint for consumption issues."""
        if endpoint.method != "GET":
            return
        await self._test_path(endpoint.path, result)

    async def _test_path(self, path: str, result: ScanResult) -> None:
        try:
            resp = await self._client.get(self._target + path)
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code != 200:
            return

        body: Any = None
        with contextlib.suppress(Exception):
            body = resp.json()

        if body is None:
            return

        await self._check_pagination(path, body, result)
        await self._check_sensitive_fields(path, body, result)

    async def _check_pagination(
        self,
        path: str,
        body: Any,
        result: ScanResult,
    ) -> None:
        """Flag list responses without pagination metadata."""
        all_keys = _flatten_keys(body)
        has_pagination = bool(all_keys & _PAGINATION_KEYS)

        # Collect all list-type values to count total items returned
        total_items = 0
        if isinstance(body, list):
            total_items = len(body)
        elif isinstance(body, dict):
            for v in body.values():
                if isinstance(v, list):
                    total_items = max(total_items, len(v))

        if total_items >= _UNPAGINATED_THRESHOLD and not has_pagination:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API10_CONSUMPTION,
                    title=f"Unbounded list response (no pagination): GET {path}",
                    severity=Severity.MEDIUM,
                    endpoint=path,
                    evidence=(
                        f"GET {path} returned {total_items} items with no pagination fields "
                        f"({', '.join(sorted(_PAGINATION_KEYS))}). "
                        "Consuming APIs may receive unbounded data volumes."
                    ),
                    remediation=(
                        "Add pagination (limit/offset or cursor-based) to all list endpoints. "
                        "Validate and cap page sizes from upstream responses."
                    ),
                    method="GET",
                )
            )

    async def _check_sensitive_fields(
        self,
        path: str,
        body: Any,
        result: ScanResult,
    ) -> None:
        """Flag responses that expose sensitive field names."""
        all_keys = _flatten_keys(body)
        exposed = all_keys & _SENSITIVE_FIELDS
        if exposed:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API10_CONSUMPTION,
                    title=f"Sensitive fields in aggregated response: GET {path}",
                    severity=Severity.HIGH,
                    endpoint=path,
                    evidence=(
                        f"Response from GET {path} contains sensitive field(s): "
                        f"{', '.join(sorted(exposed))}. "
                        "These may originate from unvalidated upstream API responses."
                    ),
                    remediation=(
                        "Filter and validate all data consumed from third-party APIs. "
                        "Never forward raw upstream responses — use explicit field allowlists."
                    ),
                    method="GET",
                )
            )
