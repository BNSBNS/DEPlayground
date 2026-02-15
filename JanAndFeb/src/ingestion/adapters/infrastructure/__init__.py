"""Infrastructure adapters - metrics, logging, etc."""

from src.ingestion.adapters.infrastructure.prometheus_metrics import PrometheusMetrics

__all__ = [
    "PrometheusMetrics",
]
