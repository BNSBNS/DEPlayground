"""Base tester ABC — shared interface for all security test modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

    from src.models import Finding, ScanResult


class BaseTester(ABC):
    """Abstract base for all OWASP API security testers.

    Each tester receives a live httpx.AsyncClient and a target URL, runs
    its specific test suite, and appends findings to a ScanResult.
    """

    def __init__(self, client: httpx.AsyncClient, target_url: str) -> None:
        self._client = client
        self._target = target_url.rstrip("/")

    @property
    @abstractmethod
    def owasp_id(self) -> str:
        """OWASP API Top 10 identifier, e.g. 'API1:2023'."""

    @abstractmethod
    async def run(self, result: ScanResult) -> None:
        """Execute all tests and append findings to result."""

    def _url(self, path: str) -> str:
        return self._target + path

    async def _get(self, path: str, **kwargs: object) -> httpx.Response:
        return await self._client.get(self._url(path), **kwargs)  # type: ignore[arg-type]

    async def _post(self, path: str, **kwargs: object) -> httpx.Response:
        return await self._client.post(self._url(path), **kwargs)  # type: ignore[arg-type]

    async def _delete(self, path: str, **kwargs: object) -> httpx.Response:
        return await self._client.delete(self._url(path), **kwargs)  # type: ignore[arg-type]

    def _finding(  # noqa: PLR0913
        self,
        owasp_category: object,
        title: str,
        severity: object,
        endpoint: str,
        evidence: str,
        remediation: str,
        method: str = "GET",
    ) -> Finding:
        from src.models import Finding  # noqa: PLC0415

        return Finding(
            owasp_category=owasp_category,  # type: ignore[arg-type]
            title=title,
            severity=severity,  # type: ignore[arg-type]
            endpoint=endpoint,
            evidence=evidence,
            remediation=remediation,
            method=method,
        )
