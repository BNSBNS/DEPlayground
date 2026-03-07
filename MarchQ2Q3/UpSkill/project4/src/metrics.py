"""Prometheus metrics for the streaming worker.

Exposed on port 9100 (configured in prometheus.yml → streaming-worker:9100).

Learning note:
  The worker tracks consumer lag (how many messages are queued but not yet processed)
  and a processed events counter. These drive the Grafana dashboard.

Usage:
    from src.metrics import CONSUMER_LAG, EVENTS_PROCESSED
    CONSUMER_LAG.labels(topic="orders", group_id="streaming-analytics").set(42)
    EVENTS_PROCESSED.labels(topic="orders").inc()
"""

from prometheus_client import Counter, Gauge, start_http_server

CONSUMER_LAG = Gauge(
    "consumer_lag_messages",
    "Number of unconsumed messages per topic partition group",
    ["topic", "group_id"],
)

EVENTS_PROCESSED = Counter(
    "events_processed_total",
    "Total events successfully processed by consumer handlers",
    ["topic"],
)

HANDLER_ERRORS = Counter(
    "handler_errors_total",
    "Total handler errors (exceptions during message processing)",
    ["topic"],
)


def start_metrics_server(port: int = 9100) -> None:
    """Start the Prometheus HTTP server on the given port.

    Call once at worker startup. Prometheus scrapes this endpoint.
    """
    start_http_server(port)
