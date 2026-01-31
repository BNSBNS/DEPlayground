"""Secondary port for metrics and observability.

This port defines the interface for recording metrics about the
ingestion process (latency, throughput, errors, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any


class MetricsPort(ABC):
    """Secondary port - defines how metrics are recorded.

    This is the driven side of the hexagonal architecture.
    Implementations include Prometheus, StatsD, CloudWatch, etc.
    """

    @abstractmethod
    def record_event_ingested(
        self,
        source: str,
        source_type: str,
        latency_ms: float,
    ) -> None:
        """Record a successfully ingested event.

        Args:
            source: Name of the data source (e.g., "finnhub")
            source_type: Type of source (e.g., "websocket")
            latency_ms: Time from event creation to ingestion in milliseconds
        """
        ...

    @abstractmethod
    def record_event_published(
        self,
        source: str,
        destination: str,
    ) -> None:
        """Record a successfully published event.

        Args:
            source: Name of the data source
            destination: Where the event was published (e.g., "kafka")
        """
        ...

    @abstractmethod
    def record_error(
        self,
        source: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """Record an error during ingestion.

        Args:
            source: Name of the data source
            error_type: Type of error (e.g., "ConnectionError", "ValidationError")
            error_message: Human-readable error description
        """
        ...

    @abstractmethod
    def record_batch_processed(
        self,
        source: str,
        batch_size: int,
        processing_time_ms: float,
    ) -> None:
        """Record a processed batch.

        Args:
            source: Name of the data source
            batch_size: Number of events in the batch
            processing_time_ms: Time to process the batch in milliseconds
        """
        ...

    @abstractmethod
    def set_connector_status(
        self,
        source: str,
        source_type: str,
        connected: bool,
    ) -> None:
        """Set the connection status of a connector.

        Args:
            source: Name of the data source
            source_type: Type of source
            connected: Whether the connector is connected
        """
        ...

    @abstractmethod
    def record_circuit_breaker_state(
        self,
        source: str,
        state: str,
    ) -> None:
        """Record circuit breaker state change.

        Args:
            source: Name of the data source
            state: Circuit breaker state (closed, open, half_open)
        """
        ...

    @abstractmethod
    def record_backpressure_event(
        self,
        source: str,
        action: str,
        buffer_size: int,
    ) -> None:
        """Record a backpressure event.

        Args:
            source: Name of the data source
            action: Action taken (blocked, dropped, sampled)
            buffer_size: Current buffer size
        """
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get current statistics.

        Returns:
            Dictionary of metric names to values
        """
        ...
