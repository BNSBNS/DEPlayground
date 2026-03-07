from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge


# Request metrics
SERVING_REQUEST_COUNT = Counter(
    "feature_store_serving_requests_total",
    "Total serving requests",
    ["endpoint", "status"],
)

SERVING_LATENCY = Histogram(
    "feature_store_serving_latency_seconds",
    "Serving request latency",
    ["endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

CACHE_HIT_RATE = Gauge(
    "feature_store_cache_hit_rate",
    "Online store cache hit rate",
    ["feature_name"],
)

# Batch compute metrics
BATCH_COMPUTE_DURATION = Histogram(
    "feature_store_batch_compute_seconds",
    "Batch compute duration",
    ["feature_set"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

BATCH_ROWS_PROCESSED = Counter(
    "feature_store_batch_rows_total",
    "Total rows processed by batch compute",
    ["feature_set"],
)

# Stream metrics
STREAM_EVENTS_PROCESSED = Counter(
    "feature_store_stream_events_total",
    "Total stream events processed",
    ["topic"],
)

STREAM_LAG = Gauge(
    "feature_store_stream_consumer_lag",
    "Stream consumer lag",
    ["topic", "partition"],
)

# Feature freshness
FEATURE_FRESHNESS_LAG = Gauge(
    "feature_store_freshness_lag_minutes",
    "Feature freshness lag in minutes",
    ["feature_name"],
)

# Drift
FEATURE_DRIFT_PSI = Gauge(
    "feature_store_drift_psi",
    "Feature drift PSI value",
    ["feature_name"],
)


def record_serving_request(endpoint: str, status: str, latency: float) -> None:
    SERVING_REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
    SERVING_LATENCY.labels(endpoint=endpoint).observe(latency)


def record_cache_hit_rate(feature_name: str, rate: float) -> None:
    CACHE_HIT_RATE.labels(feature_name=feature_name).set(rate)


def record_batch_compute(feature_set: str, duration: float, rows: int) -> None:
    BATCH_COMPUTE_DURATION.labels(feature_set=feature_set).observe(duration)
    BATCH_ROWS_PROCESSED.labels(feature_set=feature_set).inc(rows)


def record_freshness(feature_name: str, lag_minutes: float) -> None:
    FEATURE_FRESHNESS_LAG.labels(feature_name=feature_name).set(lag_minutes)


def record_drift(feature_name: str, psi: float) -> None:
    FEATURE_DRIFT_PSI.labels(feature_name=feature_name).set(psi)
