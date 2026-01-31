"""Server-Sent Events (SSE) connector (~100-500ms latency).

Uses HTTP streaming for unidirectional server-to-client communication.
"""

import asyncio
import json
from typing import Any, AsyncIterator

import httpx

from ingestion.adapters.connectors.base import BaseConnector
from ingestion.domain.models import SourceType
from ingestion.ports import MetricsPort
from ingestion.resilience import CircuitBreaker, RetryPolicy


class SSEConnector(BaseConnector):
    """SSE connector for server-sent event streams.

    Example:
        ```python
        connector = SSEConnector(
            name="dexpaprika",
            url="https://api.dexpaprika.com/sse/prices",
        )

        async for event in connector.stream_events():
            process(event)
        ```
    """

    def __init__(
        self,
        name: str,
        url: str,
        symbols: list[str] | None = None,
        headers: dict[str, str] | None = None,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10,
        timeout: float = 60.0,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize SSE connector.

        Args:
            name: Connector identifier
            url: SSE endpoint URL
            symbols: Symbols to track (used by adapter for filtering)
            headers: Optional HTTP headers
            reconnect_delay: Seconds to wait before reconnecting
            max_reconnect_attempts: Maximum reconnection attempts
            timeout: HTTP connection timeout in seconds
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            metrics: Optional metrics port
        """
        super().__init__(
            name=name,
            source_type=SourceType.SSE,
            expected_latency_ms=300,  # ~100-500ms typical
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

        self._url = url
        self._symbols = symbols or []
        self._headers = headers or {}
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_attempts = max_reconnect_attempts
        self._timeout = timeout

        self._client: httpx.AsyncClient | None = None
        self._reconnect_count = 0
        self._last_event_id: str | None = None

    async def connect(self) -> None:
        """Initialize HTTP client for SSE."""
        self._logger.info("Initializing SSE client", url=self._url)

        # Add SSE-specific headers
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            **self._headers,
        }

        # Include Last-Event-ID for resuming
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id

        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(self._timeout, connect=30.0),
        )
        self._reconnect_count = 0

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception as e:
                self._logger.warning("Error closing HTTP client", error=str(e))
            finally:
                self._client = None

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Stream SSE events."""
        if not self._client:
            raise RuntimeError("Not connected")

        try:
            async with self._client.stream("GET", self._url) as response:
                response.raise_for_status()

                event_data = ""
                event_type = "message"
                event_id = None

                async for line in response.aiter_lines():
                    if not self._running:
                        break

                    # SSE format parsing
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if event_data:
                            event_data += "\n"
                        event_data += data

                    elif line.startswith("event:"):
                        event_type = line[6:].strip()

                    elif line.startswith("id:"):
                        event_id = line[3:].strip()
                        self._last_event_id = event_id

                    elif line.startswith("retry:"):
                        # Server-suggested retry interval
                        try:
                            self._reconnect_delay = int(line[6:].strip()) / 1000.0
                        except ValueError:
                            pass

                    elif line == "":
                        # Empty line = event complete
                        if event_data:
                            try:
                                parsed = json.loads(event_data)
                                parsed["_sse_event_type"] = event_type
                                if event_id:
                                    parsed["_sse_event_id"] = event_id
                                yield parsed
                            except json.JSONDecodeError:
                                # Yield raw data if not JSON
                                yield {
                                    "data": event_data,
                                    "_sse_event_type": event_type,
                                    "_sse_event_id": event_id,
                                }

                            # Reset for next event
                            event_data = ""
                            event_type = "message"
                            event_id = None

        except httpx.HTTPStatusError as e:
            self._logger.error(
                "HTTP error",
                status_code=e.response.status_code,
                error=str(e),
            )
            raise ConnectionError(f"HTTP {e.response.status_code}: {e}")

        except httpx.RequestError as e:
            self._logger.error("Request error", error=str(e))
            raise ConnectionError(str(e))

    async def run(self) -> AsyncIterator[dict[str, Any]]:
        """Run with automatic reconnection."""
        while self._running and self._reconnect_count < self._max_reconnect_attempts:
            try:
                async for event in super().run():
                    yield event

            except ConnectionError as e:
                self._reconnect_count += 1
                self._logger.warning(
                    "Connection lost, attempting reconnect",
                    attempt=self._reconnect_count,
                    max_attempts=self._max_reconnect_attempts,
                    last_event_id=self._last_event_id,
                    error=str(e),
                )

                if self._reconnect_count < self._max_reconnect_attempts:
                    await asyncio.sleep(self._reconnect_delay)
                else:
                    raise

            except Exception:
                raise

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = super().get_stats()
        stats.update({
            "url": self._url,
            "reconnect_count": self._reconnect_count,
            "last_event_id": self._last_event_id,
        })
        return stats
