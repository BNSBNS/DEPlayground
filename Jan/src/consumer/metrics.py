"""Prometheus metrics for the trade consumer.

This module defines all metrics exposed at /metrics for Prometheus to scrape.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Message processing metrics
messages_processed = Counter(
    "messages_processed_total",
    "Total messages processed by the consumer",
    ["symbol"],
)

# DLQ metrics
dlq_messages = Counter(
    "dlq_messages_total",
    "Total messages sent to Dead Letter Queue",
    ["error_type"],
)

# Window metrics
active_windows = Gauge(
    "active_windows",
    "Number of currently active aggregation windows",
)

aggregates_written = Counter(
    "aggregates_written_total",
    "Total aggregates written to database",
    ["symbol"],
)

# Latency metrics
processing_duration = Histogram(
    "processing_duration_seconds",
    "Time spent processing each message",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

db_write_duration = Histogram(
    "db_write_duration_seconds",
    "Time spent writing to database",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Data freshness (how old is the latest processed event)
data_freshness = Gauge(
    "data_freshness_seconds",
    "Age of the most recently processed event in seconds",
)

# Consumer lag (estimated from event timestamps)
consumer_lag = Gauge(
    "consumer_lag",
    "Estimated consumer lag per partition",
    ["partition"],
)


def start_metrics_server(port: int = 8001) -> None:
    """Start the Prometheus metrics HTTP server.

    Args:
        port: Port to expose metrics on (default 8001).
    """
    start_http_server(port)
