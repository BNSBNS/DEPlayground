"""Base connector with Template Method pattern.

Defines the skeleton of the connector lifecycle while allowing
subclasses to override specific steps.
"""

import asyncio
from abc import abstractmethod
from datetime import datetime, UTC
from typing import Any, AsyncIterator

import structlog

from src.ingestion.ports import IngestionPort, MetricsPort
from src.ingestion.domain.models import SourceType, SourceMetadata
from src.ingestion.resilience import CircuitBreaker, RetryPolicy


logger = structlog.get_logger()


class BaseConnector(IngestionPort):
    """Base class for all connectors using Template Method pattern.

    Subclasses must implement:
    - connect(): Establish connection
    - disconnect(): Close connection
    - _fetch_events(): Core event fetching logic

    Subclasses may override hooks:
    - _pre_connect(): Before connection (e.g., validation)
    - _post_connect(): After connection (e.g., subscriptions)
    - _on_error(): Error handling
    - _pre_disconnect(): Before disconnect (e.g., unsubscribe)
    """

    def __init__(
        self,
        name: str,
        source_type: SourceType,
        expected_latency_ms: int,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize base connector.

        Args:
            name: Human-readable connector name
            source_type: Type of data source
            expected_latency_ms: Expected latency in milliseconds
            circuit_breaker: Optional circuit breaker for fault tolerance
            retry_policy: Optional retry policy for reconnection
            metrics: Optional metrics port for observability
        """
        self._name = name
        self._source_type = source_type
        self._expected_latency_ms = expected_latency_ms
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy or RetryPolicy()
        self._metrics = metrics

        self._connected = False
        self._running = False
        self._event_count = 0
        self._error_count = 0
        self._last_event_time: datetime | None = None

        self._logger = logger.bind(
            connector=name,
            source_type=source_type.value,
        )

    @property
    def name(self) -> str:
        """Get connector name."""
        return self._name

    @property
    def source_type(self) -> str:
        """Get source type."""
        return self._source_type.value

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    # ========== Abstract methods (must implement) ==========

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to data source."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        ...

    @abstractmethod
    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Core event fetching logic.

        Yields:
            Raw event dictionaries from the source
        """
        ...

    # ========== Hooks (may override) ==========

    async def _pre_connect(self) -> None:
        """Hook called before connect(). Override for setup."""
        self._logger.info("Preparing to connect")

    async def _post_connect(self) -> None:
        """Hook called after successful connect(). Override for subscriptions."""
        self._logger.info("Connected successfully")
        if self._metrics:
            self._metrics.set_connector_status(
                self._name, self._source_type.value, True
            )

    async def _on_error(self, error: Exception) -> None:
        """Hook called on error. Override for custom error handling."""
        self._error_count += 1
        self._logger.error(
            "Connector error",
            error=str(error),
            error_type=type(error).__name__,
            error_count=self._error_count,
        )
        if self._metrics:
            self._metrics.record_error(
                self._name, type(error).__name__, str(error)
            )

    async def _pre_disconnect(self) -> None:
        """Hook called before disconnect(). Override for cleanup."""
        self._logger.info("Preparing to disconnect")

    async def _on_event(self, event: dict[str, Any]) -> None:
        """Hook called for each event. Override for event-level processing."""
        self._event_count += 1
        self._last_event_time = datetime.now(UTC)

    # ========== Template method ==========

    async def run(self) -> AsyncIterator[dict[str, Any]]:
        """Template method - run the connector lifecycle.

        This is the main entry point that orchestrates:
        1. Pre-connect hook
        2. Connection with retry/circuit breaker
        3. Post-connect hook
        4. Event streaming
        5. Error handling
        6. Disconnection

        Yields:
            Raw event dictionaries
        """
        self._running = True

        try:
            await self._pre_connect()

            # Connect with circuit breaker if configured
            if self._circuit_breaker:
                await self._circuit_breaker.call(self.connect)
            else:
                await self.connect()

            self._connected = True
            await self._post_connect()

            # Stream events
            async for event in self._fetch_events():
                if not self._running:
                    break

                await self._on_event(event)
                yield event

        except Exception as e:
            await self._on_error(e)
            raise

        finally:
            await self._pre_disconnect()
            await self.disconnect()
            self._connected = False

            if self._metrics:
                self._metrics.set_connector_status(
                    self._name, self._source_type.value, False
                )

            self._logger.info(
                "Connector stopped",
                total_events=self._event_count,
                total_errors=self._error_count,
            )

    async def stream_events(self) -> AsyncIterator[dict[str, Any]]:
        """Stream events from the source.

        This is the IngestionPort interface method.
        Delegates to run() which implements the template method.
        """
        async for event in self.run():
            yield event

    async def health_check(self) -> bool:
        """Check connector health."""
        return self._connected and self._running

    def stop(self) -> None:
        """Signal the connector to stop."""
        self._running = False
        self._logger.info("Stop signal received")

    def create_source_metadata(self, batch_id: str | None = None) -> SourceMetadata:
        """Create source metadata for enrichment.

        Args:
            batch_id: Optional batch identifier

        Returns:
            SourceMetadata instance
        """
        return SourceMetadata(
            source_type=self._source_type,
            source_name=self._name,
            ingestion_timestamp=datetime.now(UTC),
            expected_latency_ms=self._expected_latency_ms,
            batch_id=batch_id,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = {
            "name": self._name,
            "source_type": self._source_type.value,
            "connected": self._connected,
            "running": self._running,
            "event_count": self._event_count,
            "error_count": self._error_count,
            "expected_latency_ms": self._expected_latency_ms,
            "last_event_time": (
                self._last_event_time.isoformat()
                if self._last_event_time
                else None
            ),
        }

        if self._circuit_breaker:
            stats["circuit_breaker"] = self._circuit_breaker.get_stats()

        return stats
