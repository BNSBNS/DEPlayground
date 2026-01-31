"""Prometheus metrics for the trade producer.

This module defines all metrics exposed at /metrics for Prometheus to scrape.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Trade production metrics
trades_produced = Counter(
    "trades_produced_total",
    "Total trades produced",
    ["symbol"],
)

trades_failed = Counter(
    "trades_failed_total",
    "Total trades that failed to deliver",
)

# Rate metrics
current_rate = Gauge(
    "producer_current_rate",
    "Current production rate (trades per second)",
)

burst_mode_active = Gauge(
    "producer_burst_mode",
    "Whether burst mode is currently active (1=yes, 0=no)",
)

# Latency metrics
produce_duration = Histogram(
    "produce_duration_seconds",
    "Time spent producing each trade to Kafka",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
)


def start_metrics_server(port: int = 8002) -> None:
    """Start the Prometheus metrics HTTP server.

    Args:
        port: Port to expose metrics on (default 8002).
    """
    start_http_server(port)
