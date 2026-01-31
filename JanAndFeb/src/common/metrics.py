"""Prometheus metrics for monitoring.

Q2: Monitoring Implementation

This module provides metrics collection for:
- Processing latency (P50, P95, P99)
- Message throughput
- DLQ counts
- Data freshness
- Database write latency

Usage:
    from src.common.metrics import metrics

    # Track processing time
    with metrics.processing_time():
        process_message(msg)

    # Track message count
    metrics.messages_processed.inc()

    # Track data freshness
    metrics.update_data_freshness(event_timestamp, now)
"""

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        start_http_server,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsCollector:
    """Collects and exposes Prometheus metrics.

    Metrics exposed:
    - messages_processed_total: Counter of processed messages
    - dlq_messages_total: Counter of DLQ messages
    - processing_duration_seconds: Histogram of processing time
    - db_write_duration_seconds: Histogram of DB write time
    - data_freshness_seconds: Gauge of data freshness (lag)
    - active_windows: Gauge of active aggregation windows
    - consumer_lag: Gauge of Kafka consumer lag
    """

    def __init__(self, port: int = 8000) -> None:
        """Initialize metrics collector.

        Args:
            port: Port to expose metrics on (default 8000)
        """
        self._port = port
        self._started = False

        if PROMETHEUS_AVAILABLE:
            # Counters
            self.messages_processed = Counter(
                'messages_processed_total',
                'Total number of messages processed',
                ['symbol', 'status']  # status: success, error
            )

            self.dlq_messages = Counter(
                'dlq_messages_total',
                'Total number of messages sent to DLQ',
                ['error_type']
            )

            self.aggregates_written = Counter(
                'aggregates_written_total',
                'Total number of aggregates written to database',
                ['symbol']
            )

            # Histograms
            self.processing_duration = Histogram(
                'processing_duration_seconds',
                'Time spent processing messages',
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
            )

            self.db_write_duration = Histogram(
                'db_write_duration_seconds',
                'Time spent writing to database',
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
            )

            # Gauges
            self.data_freshness = Gauge(
                'data_freshness_seconds',
                'Seconds between event time and processing time',
                ['symbol']
            )

            self.active_windows = Gauge(
                'active_windows',
                'Number of active aggregation windows'
            )

            self.consumer_lag = Gauge(
                'consumer_lag',
                'Kafka consumer lag (messages behind)',
                ['partition']
            )

    def start_server(self) -> None:
        """Start the Prometheus metrics HTTP server."""
        if PROMETHEUS_AVAILABLE and not self._started:
            start_http_server(self._port)
            self._started = True

    @contextmanager
    def processing_time(self) -> Iterator[None]:
        """Context manager to track processing duration.

        Example:
            with metrics.processing_time():
                process_message(msg)
        """
        if PROMETHEUS_AVAILABLE:
            start = time.perf_counter()
            try:
                yield
            finally:
                self.processing_duration.observe(time.perf_counter() - start)
        else:
            yield

    @contextmanager
    def db_write_time(self) -> Iterator[None]:
        """Context manager to track DB write duration.

        Example:
            with metrics.db_write_time():
                db.write(aggregate)
        """
        if PROMETHEUS_AVAILABLE:
            start = time.perf_counter()
            try:
                yield
            finally:
                self.db_write_duration.observe(time.perf_counter() - start)
        else:
            yield

    def update_data_freshness(
        self,
        event_time: datetime,
        processing_time: datetime,
        symbol: str = "all"
    ) -> float:
        """Update data freshness metric.

        Q3: Data Freshness Implementation

        Freshness = processing_time - event_time
        - < 5s: Good (green)
        - 5-30s: Warning (yellow)
        - > 30s: Critical (red)

        Args:
            event_time: When the trade event occurred
            processing_time: When we processed it
            symbol: Trading symbol for labeling

        Returns:
            Freshness in seconds
        """
        freshness = (processing_time - event_time).total_seconds()

        if PROMETHEUS_AVAILABLE:
            self.data_freshness.labels(symbol=symbol).set(freshness)

        return freshness

    def record_message_processed(self, symbol: str, success: bool = True) -> None:
        """Record a processed message.

        Args:
            symbol: Trading symbol
            success: Whether processing succeeded
        """
        if PROMETHEUS_AVAILABLE:
            status = "success" if success else "error"
            self.messages_processed.labels(symbol=symbol, status=status).inc()

    def record_dlq_message(self, error_type: str) -> None:
        """Record a DLQ message.

        Args:
            error_type: Type of error (e.g., ValidationError)
        """
        if PROMETHEUS_AVAILABLE:
            self.dlq_messages.labels(error_type=error_type).inc()

    def record_aggregate_written(self, symbol: str) -> None:
        """Record an aggregate written to database.

        Args:
            symbol: Trading symbol
        """
        if PROMETHEUS_AVAILABLE:
            self.aggregates_written.labels(symbol=symbol).inc()

    def set_active_windows(self, count: int) -> None:
        """Set the active window count.

        Args:
            count: Number of active windows
        """
        if PROMETHEUS_AVAILABLE:
            self.active_windows.set(count)

    def set_consumer_lag(self, partition: int, lag: int) -> None:
        """Set consumer lag for a partition.

        Args:
            partition: Kafka partition number
            lag: Number of messages behind
        """
        if PROMETHEUS_AVAILABLE:
            self.consumer_lag.labels(partition=str(partition)).set(lag)


# Global metrics instance
metrics = MetricsCollector()


# Data freshness checker for database-level validation
class DataFreshnessChecker:
    """Check data freshness in the database.

    Q3: Data Freshness - Validates that data in the database
    is up-to-date and meets SLO requirements.

    SLO: 99% of data should be < 5 seconds stale
    """

    def __init__(self, db_writer: "DatabaseWriter") -> None:  # type: ignore
        """Initialize freshness checker.

        Args:
            db_writer: Database writer instance
        """
        self._db = db_writer

    def check_freshness(self, max_age_seconds: int = 60) -> dict:
        """Check data freshness in the database.

        Args:
            max_age_seconds: Maximum acceptable age

        Returns:
            Dictionary with freshness metrics
        """
        # Query: Get the most recent window_start per symbol
        sql = """
            SELECT
                symbol,
                MAX(window_start) as latest_window,
                NOW() - MAX(window_start) as staleness
            FROM trade_aggregates
            WHERE window_start >= NOW() - INTERVAL '1 hour'
            GROUP BY symbol
            ORDER BY staleness DESC
        """

        try:
            with self._db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    results = cur.fetchall()

            stale_symbols = []
            fresh_symbols = []

            for row in results:
                staleness_seconds = row['staleness'].total_seconds()
                if staleness_seconds > max_age_seconds:
                    stale_symbols.append({
                        'symbol': row['symbol'],
                        'staleness_seconds': staleness_seconds
                    })
                else:
                    fresh_symbols.append(row['symbol'])

            return {
                'is_fresh': len(stale_symbols) == 0,
                'stale_symbols': stale_symbols,
                'fresh_symbols': fresh_symbols,
                'max_staleness_seconds': max(
                    (s['staleness_seconds'] for s in stale_symbols),
                    default=0
                )
            }
        except Exception as e:
            return {
                'is_fresh': False,
                'error': str(e)
            }

    def get_freshness_sql(self) -> str:
        """Get SQL query for manual freshness check.

        Returns:
            SQL query string
        """
        return """
-- Q3: Data Freshness Check Query
-- Run this to validate data is fresh

SELECT
    symbol,
    MAX(window_start) as latest_window,
    NOW() - MAX(window_start) as staleness,
    CASE
        WHEN NOW() - MAX(window_start) < INTERVAL '5 seconds' THEN 'FRESH'
        WHEN NOW() - MAX(window_start) < INTERVAL '30 seconds' THEN 'WARNING'
        ELSE 'STALE'
    END as status
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY staleness DESC;

-- Expected during active trading:
-- All symbols should show 'FRESH' status
-- staleness should be < 5 seconds
"""
