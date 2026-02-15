"""Polling connector for REST APIs (configurable interval).

Periodically fetches data from REST endpoints.
"""

import asyncio
from datetime import datetime, UTC
from typing import Any, AsyncIterator

import httpx

from src.ingestion.adapters.connectors.base import BaseConnector
from src.ingestion.domain.models import SourceType
from src.ingestion.ports import MetricsPort
from src.ingestion.resilience import CircuitBreaker, RetryPolicy, RateLimiter


class PollingConnector(BaseConnector):
    """Polling connector for REST APIs.

    Example:
        ```python
        connector = PollingConnector(
            name="entsoe",
            url="https://web-api.tp.entsoe.eu/api",
            poll_interval=300,  # 5 minutes
            api_key="your-api-key",
        )

        async for events in connector.stream_events():
            for event in events:
                process(event)
        ```
    """

    def __init__(
        self,
        name: str,
        url: str,
        poll_interval: int = 300,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize polling connector.

        Args:
            name: Connector identifier
            url: REST API endpoint URL
            poll_interval: Seconds between polls
            api_key: Optional API key
            headers: Optional HTTP headers
            params: Optional query parameters
            timeout: HTTP request timeout
            rate_limiter: Optional rate limiter for API quota
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            metrics: Optional metrics port
        """
        super().__init__(
            name=name,
            source_type=SourceType.POLLING,
            expected_latency_ms=poll_interval * 1000,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

        self._url = url
        self._poll_interval = poll_interval
        self._api_key = api_key
        self._headers = headers or {}
        self._params = params or {}
        self._timeout = timeout
        self._rate_limiter = rate_limiter

        self._client: httpx.AsyncClient | None = None
        self._last_poll_time: datetime | None = None
        self._poll_count = 0

    async def connect(self) -> None:
        """Initialize HTTP client."""
        self._logger.info("Initializing polling client", url=self._url)

        headers = self._headers.copy()
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(self._timeout),
        )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception as e:
                self._logger.warning("Error closing HTTP client", error=str(e))
            finally:
                self._client = None

    async def _make_request(self) -> dict[str, Any] | list[dict[str, Any]]:
        """Make HTTP request to the endpoint.

        Override this method for custom request logic.

        Returns:
            Response data (dict or list of dicts)
        """
        if not self._client:
            raise RuntimeError("Not connected")

        # Respect rate limits
        if self._rate_limiter:
            await self._rate_limiter.acquire()

        response = await self._client.get(self._url, params=self._params)
        response.raise_for_status()

        return response.json()

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Poll and yield events at configured interval."""
        while self._running:
            try:
                self._poll_count += 1
                self._last_poll_time = datetime.now(UTC)

                self._logger.debug(
                    "Polling",
                    poll_count=self._poll_count,
                    url=self._url,
                )

                data = await self._make_request()

                # Handle both single dict and list responses
                if isinstance(data, list):
                    for item in data:
                        yield item
                else:
                    yield data

            except httpx.HTTPStatusError as e:
                self._logger.error(
                    "HTTP error during poll",
                    status_code=e.response.status_code,
                    error=str(e),
                )
                # Continue polling despite errors
                await self._on_error(e)

            except httpx.RequestError as e:
                self._logger.error("Request error during poll", error=str(e))
                await self._on_error(e)

            # Wait for next poll interval
            if self._running:
                await asyncio.sleep(self._poll_interval)

    def set_poll_interval(self, seconds: int) -> None:
        """Update the polling interval.

        Args:
            seconds: New interval in seconds
        """
        self._poll_interval = seconds
        self._expected_latency_ms = seconds * 1000
        self._logger.info("Poll interval updated", interval=seconds)

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = super().get_stats()
        stats.update({
            "url": self._url,
            "poll_interval": self._poll_interval,
            "poll_count": self._poll_count,
            "last_poll_time": (
                self._last_poll_time.isoformat()
                if self._last_poll_time
                else None
            ),
        })
        return stats
