"""Prometheus metrics for the trade consumer.

This module defines all metrics exposed at /metrics for Prometheus to scrape.

Key improvements:
1. True Kafka lag metrics (offset-based, not timestamp-based)
2. Backpressure and flow control metrics
3. Memory usage metrics for aggregator
4. Commit success/failure tracking
"""

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

# =============================================================================
# Message Processing Metrics
# =============================================================================

messages_processed = Counter(
    "messages_processed_total",
    "Total messages processed by the consumer",
    ["symbol"],
)

messages_received = Counter(
    "messages_received_total",
    "Total messages received from Kafka (before processing)",
    ["partition"],
)

# =============================================================================
# DLQ Metrics
# =============================================================================

dlq_messages = Counter(
    "dlq_messages_total",
    "Total messages sent to Dead Letter Queue",
    ["error_type"],
)

# =============================================================================
# Window Metrics
# =============================================================================

active_windows = Gauge(
    "active_windows",
    "Number of currently active aggregation windows",
)

aggregates_written = Counter(
    "aggregates_written_total",
    "Total aggregates written to database",
    ["symbol"],
)

window_evictions = Counter(
    "window_evictions_total",
    "Total windows evicted due to memory limits",
)

# =============================================================================
# Latency Metrics
# =============================================================================

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

# =============================================================================
# Data Freshness (Event Timestamp Age)
# =============================================================================

data_freshness = Gauge(
    "data_freshness_seconds",
    "Age of the most recently processed event in seconds (event time vs wall clock)",
)

# =============================================================================
# True Kafka Consumer Lag (Offset-Based)
# =============================================================================

# This is the CORRECT way to measure Kafka consumer lag:
# lag = high_watermark_offset - committed_offset
# NOT: now() - event_timestamp (which is data freshness, not lag)

kafka_consumer_lag = Gauge(
    "kafka_consumer_lag_offsets",
    "True Kafka consumer lag per partition (high_watermark - committed_offset)",
    ["partition"],
)

kafka_high_watermark = Gauge(
    "kafka_high_watermark_offset",
    "Latest offset in each partition (high watermark)",
    ["partition"],
)

kafka_committed_offset = Gauge(
    "kafka_committed_offset",
    "Last committed offset per partition",
    ["partition"],
)

kafka_processed_offset = Gauge(
    "kafka_processed_offset",
    "Last processed (but possibly not yet committed) offset per partition",
    ["partition"],
)

total_consumer_lag = Gauge(
    "kafka_consumer_lag_total",
    "Total consumer lag across all partitions",
)

# Legacy metric - kept for backward compatibility but deprecated
# Use kafka_consumer_lag_offsets instead
consumer_lag = Gauge(
    "consumer_lag",
    "DEPRECATED: Event timestamp age per partition. Use kafka_consumer_lag_offsets for true lag.",
    ["partition"],
)

# =============================================================================
# Offset Commit Metrics
# =============================================================================

offset_commits_total = Counter(
    "offset_commits_total",
    "Total offset commit attempts",
    ["status"],  # success, failed, retried
)

offset_commit_retries = Counter(
    "offset_commit_retries_total",
    "Total offset commit retry attempts",
)

offset_commit_duration = Histogram(
    "offset_commit_duration_seconds",
    "Time spent committing offsets",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

uncommitted_offsets = Gauge(
    "uncommitted_offsets",
    "Number of processed but uncommitted offsets per partition",
    ["partition"],
)

# =============================================================================
# Backpressure and Flow Control Metrics
# =============================================================================

backpressure_state = Gauge(
    "backpressure_state",
    "Current backpressure state (0=flowing, 1=throttled, 2=paused)",
)

backpressure_pauses = Counter(
    "backpressure_pauses_total",
    "Total number of times consumption was paused due to backpressure",
)

backpressure_resumes = Counter(
    "backpressure_resumes_total",
    "Total number of times consumption was resumed after backpressure",
)

messages_in_flight = Gauge(
    "messages_in_flight",
    "Number of messages currently being processed (between receive and commit)",
)

processing_throughput = Gauge(
    "processing_throughput_per_second",
    "Current message processing throughput (messages/second)",
)

# =============================================================================
# Memory Metrics
# =============================================================================

aggregator_memory_bytes = Gauge(
    "aggregator_memory_bytes",
    "Estimated memory usage of the windowed aggregator in bytes",
)

aggregator_memory_limit_bytes = Gauge(
    "aggregator_memory_limit_bytes",
    "Maximum allowed memory for the aggregator in bytes",
)

# =============================================================================
# Consumer Info
# =============================================================================

consumer_info = Info(
    "consumer",
    "Consumer metadata and configuration",
)


def start_metrics_server(port: int = 8001) -> None:
    """Start the Prometheus metrics HTTP server.

    Args:
        port: Port to expose metrics on (default 8001).
    """
    start_http_server(port)


def update_lag_metrics(
    partition: int,
    high_watermark: int,
    committed_offset: int,
    processed_offset: int,
) -> None:
    """Update all lag-related metrics for a partition.

    This is the recommended way to update lag metrics, ensuring
    all related metrics stay consistent.

    Args:
        partition: The Kafka partition number
        high_watermark: Latest offset in the partition
        committed_offset: Last committed offset
        processed_offset: Last processed offset
    """
    # Calculate true lag
    lag = max(0, high_watermark - committed_offset - 1)

    # Update all metrics
    kafka_consumer_lag.labels(partition=str(partition)).set(lag)
    kafka_high_watermark.labels(partition=str(partition)).set(high_watermark)
    kafka_committed_offset.labels(partition=str(partition)).set(committed_offset)
    kafka_processed_offset.labels(partition=str(partition)).set(processed_offset)

    # Update uncommitted count
    uncommitted = max(0, processed_offset - committed_offset)
    uncommitted_offsets.labels(partition=str(partition)).set(uncommitted)


def update_total_lag(total_lag: int) -> None:
    """Update the total lag across all partitions.

    Args:
        total_lag: Sum of lag across all partitions
    """
    total_consumer_lag.set(total_lag)


def record_offset_commit(success: bool, retried: bool = False) -> None:
    """Record an offset commit attempt.

    Args:
        success: Whether the commit succeeded
        retried: Whether this was a retry attempt
    """
    if success:
        offset_commits_total.labels(status="success").inc()
    else:
        offset_commits_total.labels(status="failed").inc()

    if retried:
        offset_commits_total.labels(status="retried").inc()
        offset_commit_retries.inc()


def update_backpressure_state(state: str) -> None:
    """Update backpressure state metric.

    Args:
        state: One of "flowing", "throttled", "paused"
    """
    state_values = {"flowing": 0, "throttled": 1, "paused": 2}
    backpressure_state.set(state_values.get(state, 0))


def update_aggregator_memory(current_bytes: int, limit_bytes: int) -> None:
    """Update aggregator memory metrics.

    Args:
        current_bytes: Current estimated memory usage
        limit_bytes: Maximum allowed memory
    """
    aggregator_memory_bytes.set(current_bytes)
    aggregator_memory_limit_bytes.set(limit_bytes)
