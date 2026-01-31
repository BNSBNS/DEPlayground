"""Infrastructure adapters - metrics, logging, etc."""

from ingestion.adapters.infrastructure.prometheus_metrics import PrometheusMetrics

__all__ = [
    "PrometheusMetrics",
]
