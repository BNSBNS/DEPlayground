"""WebSocket connector for real-time streaming (~20-170ms latency).

Supports automatic reconnection and subscription management.
"""

import asyncio
import json
from typing import Any, AsyncIterator

import websockets
from websockets.client import WebSocketClientProtocol

from src.ingestion.adapters.connectors.base import BaseConnector
from src.ingestion.domain.models import SourceType
from src.ingestion.ports import MetricsPort
from src.ingestion.resilience import CircuitBreaker, RetryPolicy


class WebSocketConnector(BaseConnector):
    """WebSocket connector for real-time data streams.

    Example:
        ```python
        connector = WebSocketConnector(
            name="finnhub",
            url="wss://ws.finnhub.io",
            api_key="your-api-key",
            symbols=["AAPL", "GOOGL", "BINANCE:BTCUSDT"],
        )

        async for event in connector.stream_events():
            process(event)
        ```
    """

    def __init__(
        self,
        name: str,
        url: str,
        api_key: str | None = None,
        symbols: list[str] | None = None,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize WebSocket connector.

        Args:
            name: Connector identifier
            url: WebSocket URL
            api_key: Optional API key for authentication
            symbols: List of symbols to subscribe to
            reconnect_delay: Seconds to wait before reconnecting
            max_reconnect_attempts: Maximum reconnection attempts
            ping_interval: Seconds between ping messages
            ping_timeout: Seconds to wait for pong response
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            metrics: Optional metrics port
        """
        super().__init__(
            name=name,
            source_type=SourceType.WEBSOCKET,
            expected_latency_ms=100,  # ~20-170ms typical
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

        self._url = url
        self._api_key = api_key
        self._symbols = symbols or []
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_attempts = max_reconnect_attempts
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout

        self._ws: WebSocketClientProtocol | None = None
        self._reconnect_count = 0

    def _build_url(self) -> str:
        """Build WebSocket URL with authentication."""
        if self._api_key:
            separator = "&" if "?" in self._url else "?"
            return f"{self._url}{separator}token={self._api_key}"
        return self._url

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        url = self._build_url()
        self._logger.info("Connecting to WebSocket", url=self._url)

        self._ws = await websockets.connect(
            url,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
        )
        self._reconnect_count = 0

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                self._logger.warning("Error closing WebSocket", error=str(e))
            finally:
                self._ws = None

    async def _post_connect(self) -> None:
        """Subscribe to symbols after connection."""
        await super()._post_connect()

        for symbol in self._symbols:
            await self._subscribe(symbol)
            self._logger.debug("Subscribed to symbol", symbol=symbol)

    async def _subscribe(self, symbol: str) -> None:
        """Subscribe to a symbol.

        Override this method for different subscription formats.
        Default format is for Finnhub.
        """
        if self._ws:
            message = json.dumps({"type": "subscribe", "symbol": symbol})
            await self._ws.send(message)

    async def _unsubscribe(self, symbol: str) -> None:
        """Unsubscribe from a symbol."""
        if self._ws:
            message = json.dumps({"type": "unsubscribe", "symbol": symbol})
            await self._ws.send(message)

    async def _pre_disconnect(self) -> None:
        """Unsubscribe from all symbols before disconnecting."""
        await super()._pre_disconnect()

        for symbol in self._symbols:
            try:
                await self._unsubscribe(symbol)
            except Exception:
                pass  # Best effort unsubscribe

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Receive and yield WebSocket messages."""
        if not self._ws:
            raise RuntimeError("Not connected")

        try:
            async for message in self._ws:
                if not self._running:
                    break

                try:
                    data = json.loads(message)
                    yield data
                except json.JSONDecodeError as e:
                    self._logger.warning(
                        "Invalid JSON received",
                        message=str(message)[:100],
                        error=str(e),
                    )

        except websockets.ConnectionClosed as e:
            self._logger.warning(
                "WebSocket connection closed",
                code=e.code,
                reason=e.reason,
            )
            raise ConnectionError(f"WebSocket closed: {e.reason}")

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
                    error=str(e),
                )

                if self._reconnect_count < self._max_reconnect_attempts:
                    await asyncio.sleep(self._reconnect_delay)
                else:
                    raise

            except Exception:
                # Non-connection errors stop the connector
                raise

    def add_symbol(self, symbol: str) -> None:
        """Add a symbol to subscribe to.

        If already connected, subscribes immediately.
        """
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            if self._connected and self._ws:
                asyncio.create_task(self._subscribe(symbol))

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol subscription.

        If connected, unsubscribes immediately.
        """
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            if self._connected and self._ws:
                asyncio.create_task(self._unsubscribe(symbol))

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = super().get_stats()
        stats.update({
            "url": self._url,
            "symbols": self._symbols,
            "reconnect_count": self._reconnect_count,
            "max_reconnect_attempts": self._max_reconnect_attempts,
        })
        return stats
