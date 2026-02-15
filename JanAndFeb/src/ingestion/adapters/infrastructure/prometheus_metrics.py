"""Prometheus metrics adapter.

Implements the MetricsPort interface using Prometheus client.
"""

from typing import Any

from prometheus_client import Counter, Gauge, Histogram, start_http_server
import structlog

from src.ingestion.ports import MetricsPort


logger = structlog.get_logger()


class PrometheusMetrics(MetricsPort):
    """Prometheus metrics implementation.

    Provides metrics for monitoring the ingestion pipeline:
    - Event counters (by source, type)
    - Latency histograms
    - Error counters
    - Connection status gauges
    - Circuit breaker states
    - Backpressure events

    Example:
        ```python
        metrics = PrometheusMetrics(port=8003)
        metrics.start_server()

        metrics.record_event_ingested("finnhub", "websocket", 50.0)
        ```
    """

    def __init__(self, port: int = 8003, namespace: str = "ingestion"):
        """Initialize Prometheus metrics.

        Args:
            port: HTTP port for metrics endpoint
            namespace: Metric name prefix
        """
        self._port = port
        self._namespace = namespace
        self._server_started = False

        # Event counters
        self._events_ingested = Counter(
            f"{namespace}_events_ingested_total",
            "Total events ingested",
            ["source", "source_type"],
        )

        self._events_published = Counter(
            f"{namespace}_events_published_total",
            "Total events published",
            ["source", "destination"],
        )

        self._events_dropped = Counter(
            f"{namespace}_events_dropped_total",
            "Total events dropped",
            ["source", "reason"],
        )

        # Error counters
        self._errors = Counter(
            f"{namespace}_errors_total",
            "Total errors",
            ["source", "error_type"],
        )

        # Latency histograms
        self._ingestion_latency = Histogram(
            f"{namespace}_ingestion_latency_ms",
            "Ingestion latency in milliseconds",
            ["source"],
            buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
        )

        self._publish_latency = Histogram(
            f"{namespace}_publish_latency_ms",
            "Publishing latency in milliseconds",
            ["destination"],
            buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
        )

        # Batch metrics
        self._batch_size = Histogram(
            f"{namespace}_batch_size",
            "Batch size distribution",
            ["source"],
            buckets=(1, 10, 50, 100, 500, 1000, 5000, 10000),
        )

        self._batch_processing_time = Histogram(
            f"{namespace}_batch_processing_ms",
            "Batch processing time in milliseconds",
            ["source"],
            buckets=(10, 50, 100, 500, 1000, 5000, 10000, 30000),
        )

        # Connection status
        self._connector_status = Gauge(
            f"{namespace}_connector_status",
            "Connector connection status (1=connected, 0=disconnected)",
            ["source", "source_type"],
        )

        # Circuit breaker
        self._circuit_breaker_state = Gauge(
            f"{namespace}_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half_open)",
            ["source"],
        )

        # Backpressure
        self._backpressure_events = Counter(
            f"{namespace}_backpressure_events_total",
            "Backpressure events",
            ["source", "action"],
        )

        self._buffer_size = Gauge(
            f"{namespace}_buffer_size",
            "Current buffer size",
            ["source"],
        )

    def start_server(self) -> None:
        """Start the Prometheus HTTP server."""
        if not self._server_started:
            start_http_server(self._port)
            self._server_started = True
            logger.info("Prometheus metrics server started", port=self._port)

    def record_event_ingested(
        self,
        source: str,
        source_type: str,
        latency_ms: float,
    ) -> None:
        """Record a successfully ingested event."""
        self._events_ingested.labels(source=source, source_type=source_type).inc()
        self._ingestion_latency.labels(source=source).observe(latency_ms)

    def record_event_published(
        self,
        source: str,
        destination: str,
    ) -> None:
        """Record a successfully published event."""
        self._events_published.labels(source=source, destination=destination).inc()

    def record_error(
        self,
        source: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """Record an error."""
        self._errors.labels(source=source, error_type=error_type).inc()

    def record_batch_processed(
        self,
        source: str,
        batch_size: int,
        processing_time_ms: float,
    ) -> None:
        """Record a processed batch."""
        self._batch_size.labels(source=source).observe(batch_size)
        self._batch_processing_time.labels(source=source).observe(processing_time_ms)

    def set_connector_status(
        self,
        source: str,
        source_type: str,
        connected: bool,
    ) -> None:
        """Set connector connection status."""
        self._connector_status.labels(
            source=source, source_type=source_type
        ).set(1 if connected else 0)

    def record_circuit_breaker_state(
        self,
        source: str,
        state: str,
    ) -> None:
        """Record circuit breaker state."""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, -1)
        self._circuit_breaker_state.labels(source=source).set(state_value)

    def record_backpressure_event(
        self,
        source: str,
        action: str,
        buffer_size: int,
    ) -> None:
        """Record a backpressure event."""
        self._backpressure_events.labels(source=source, action=action).inc()
        self._buffer_size.labels(source=source).set(buffer_size)

    def record_event_dropped(
        self,
        source: str,
        reason: str,
    ) -> None:
        """Record a dropped event."""
        self._events_dropped.labels(source=source, reason=reason).inc()

    def record_publish_latency(
        self,
        destination: str,
        latency_ms: float,
    ) -> None:
        """Record publishing latency."""
        self._publish_latency.labels(destination=destination).observe(latency_ms)

    def set_buffer_size(
        self,
        source: str,
        size: int,
    ) -> None:
        """Set current buffer size."""
        self._buffer_size.labels(source=source).set(size)

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        # Note: This returns a snapshot, not the full Prometheus data
        return {
            "port": self._port,
            "namespace": self._namespace,
            "server_started": self._server_started,
        }
