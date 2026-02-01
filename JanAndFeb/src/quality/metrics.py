"""Prometheus metrics for data quality monitoring.

These metrics allow tracking data quality in Grafana dashboards:
- Overall quality score per source/symbol
- Validation failure counts by type
- Data freshness (time since last valid record)
- Completeness (percentage of non-null fields)
"""

from prometheus_client import Counter, Gauge, Histogram

# Quality score gauge (0-1 scale)
data_quality_score = Gauge(
    "data_quality_score",
    "Overall data quality score (0=bad, 1=perfect)",
    ["source", "check_type"],
)

# Validation failure counter
validation_failures_total = Counter(
    "validation_failures_total",
    "Total number of validation failures",
    ["source", "failure_type", "symbol"],
)

# Records processed
records_processed_total = Counter(
    "records_processed_total",
    "Total records processed through quality checks",
    ["source", "result"],  # result: valid, invalid, skipped
)

# Freshness gauge (seconds since last valid record)
data_freshness_seconds = Gauge(
    "data_freshness_seconds",
    "Seconds since last valid record was received",
    ["source", "symbol"],
)

# Completeness gauge (percentage of non-null fields)
data_completeness_ratio = Gauge(
    "data_completeness_ratio",
    "Ratio of non-null fields (0-1)",
    ["source", "symbol"],
)

# Quality check latency
quality_check_duration_seconds = Histogram(
    "quality_check_duration_seconds",
    "Time spent on quality checks",
    ["check_type"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Duplicate detection
duplicates_detected_total = Counter(
    "duplicates_detected_total",
    "Total duplicate records detected",
    ["source", "symbol"],
)

# Schema violations
schema_violations_total = Counter(
    "schema_violations_total",
    "Total schema violation errors",
    ["source", "field", "violation_type"],
)


def record_quality_check(
    source: str,
    check_type: str,
    score: float,
    duration_seconds: float | None = None,
) -> None:
    """Record a quality check result.

    Args:
        source: Data source name (e.g., "finnhub", "synthetic")
        check_type: Type of check (e.g., "completeness", "validity")
        score: Quality score (0-1)
        duration_seconds: Optional check duration
    """
    data_quality_score.labels(source=source, check_type=check_type).set(score)
    if duration_seconds is not None:
        quality_check_duration_seconds.labels(check_type=check_type).observe(
            duration_seconds
        )


def record_validation_failure(
    source: str,
    failure_type: str,
    symbol: str = "unknown",
) -> None:
    """Record a validation failure.

    Args:
        source: Data source name
        failure_type: Type of failure (e.g., "null_price", "invalid_symbol")
        symbol: Symbol that failed validation
    """
    validation_failures_total.labels(
        source=source,
        failure_type=failure_type,
        symbol=symbol,
    ).inc()
    records_processed_total.labels(source=source, result="invalid").inc()


def record_valid_record(source: str) -> None:
    """Record a valid record processed.

    Args:
        source: Data source name
    """
    records_processed_total.labels(source=source, result="valid").inc()


def record_freshness(source: str, symbol: str, seconds_since_last: float) -> None:
    """Record data freshness.

    Args:
        source: Data source name
        symbol: Trading symbol
        seconds_since_last: Seconds since last valid record
    """
    data_freshness_seconds.labels(source=source, symbol=symbol).set(seconds_since_last)


def record_completeness(source: str, symbol: str, ratio: float) -> None:
    """Record field completeness ratio.

    Args:
        source: Data source name
        symbol: Trading symbol
        ratio: Ratio of non-null fields (0-1)
    """
    data_completeness_ratio.labels(source=source, symbol=symbol).set(ratio)


def record_duplicate(source: str, symbol: str) -> None:
    """Record a duplicate detection.

    Args:
        source: Data source name
        symbol: Trading symbol
    """
    duplicates_detected_total.labels(source=source, symbol=symbol).inc()


def record_schema_violation(
    source: str,
    field: str,
    violation_type: str,
) -> None:
    """Record a schema violation.

    Args:
        source: Data source name
        field: Field that violated schema
        violation_type: Type of violation (e.g., "type_mismatch", "out_of_range")
    """
    schema_violations_total.labels(
        source=source,
        field=field,
        violation_type=violation_type,
    ).inc()
