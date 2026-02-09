"""PostgreSQL database writer with idempotent upserts.

This module provides a database writer that ensures idempotent writes
using INSERT ... ON CONFLICT for at-least-once streaming semantics.
"""

import time
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.common.config import PostgresSettings, get_settings
from src.common.logging_config import get_logger
from src.common.models import DLQMessage, TradeAggregate

logger = get_logger(__name__)

# Import metrics - handle circular import by lazy import
_metrics = None


def _get_metrics():
    """Lazy import metrics to avoid circular dependency."""
    global _metrics
    if _metrics is None:
        from src.consumer import metrics

        _metrics = metrics
    return _metrics


class DatabaseWriter:
    """PostgreSQL writer with idempotent upsert semantics.

    Uses INSERT ... ON CONFLICT to handle duplicate writes that may occur
    during consumer restarts or reprocessing. This ensures correctness
    with at-least-once delivery semantics.
    """

    # SQL for idempotent upsert of trade aggregates.
    # total_value is NOT persisted: it is an in-flight intermediate used to
    # derive vwap. Once vwap is computed and stored it is no longer needed.
    UPSERT_AGGREGATE_SQL = """
        INSERT INTO trade_aggregates (
            symbol, window_start, window_end, vwap, total_volume,
            trade_count, max_price, min_price,
            lmp, lmp_energy, lmp_congestion, lmp_loss,
            created_at, updated_at
        )
        VALUES (
            %(symbol)s, %(window_start)s, %(window_end)s, %(vwap)s, %(total_volume)s,
            %(trade_count)s, %(max_price)s, %(min_price)s,
            %(lmp)s, %(lmp_energy)s, %(lmp_congestion)s, %(lmp_loss)s,
            NOW(), NOW()
        )
        ON CONFLICT (symbol, window_start) DO UPDATE SET
            vwap = EXCLUDED.vwap,
            total_volume = EXCLUDED.total_volume,
            trade_count = EXCLUDED.trade_count,
            max_price = EXCLUDED.max_price,
            min_price = EXCLUDED.min_price,
            window_end = EXCLUDED.window_end,
            lmp = EXCLUDED.lmp,
            lmp_energy = EXCLUDED.lmp_energy,
            lmp_congestion = EXCLUDED.lmp_congestion,
            lmp_loss = EXCLUDED.lmp_loss,
            updated_at = NOW()
    """

    # SQL for inserting DLQ tracking records
    INSERT_DLQ_SQL = """
        INSERT INTO dlq_messages (
            original_message, error_type, error_message, failed_at,
            consumer_group, kafka_partition, kafka_offset
        )
        VALUES (
            %(original_message)s, %(error_type)s, %(error_message)s,
            %(failed_at)s, %(consumer_group)s, %(partition)s, %(offset)s
        )
    """

    def __init__(
        self,
        settings: PostgresSettings | None = None,
    ) -> None:
        """Initialize the database writer with connection pool.

        Args:
            settings: PostgreSQL connection settings.
        """
        if settings is None:
            settings = get_settings().postgres

        self._settings = settings
        self._dsn = settings.get_dsn()

        # Initialize connection pool
        self._pool = ConnectionPool(
            conninfo=self._dsn,
            min_size=settings.pool_min,
            max_size=settings.pool_max,
            timeout=settings.pool_timeout,
            max_lifetime=settings.pool_recycle,
            kwargs={
                "row_factory": dict_row,
                "autocommit": False,
            },
        )

        logger.info(
            "Database writer initialized with connection pool",
            host=settings.host,
            database=settings.db,
            pool_min=settings.pool_min,
            pool_max=settings.pool_max,
        )

    @contextmanager
    def _get_connection(self) -> Iterator[psycopg.Connection[dict[str, object]]]:
        """Get a database connection from the pool.

        Automatically handles pre-ping health checks if configured.
        On OperationalError, the connection is automatically returned to pool for cleanup.
        """
        conn = None
        try:
            conn = self._pool.getconn()

            # Pre-ping health check if enabled
            if self._settings.pool_pre_ping:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                except psycopg.OperationalError:
                    # Connection is stale, close and get a new one
                    self._pool.putconn(conn, close=True)
                    conn = self._pool.getconn()
                    logger.debug("Replaced stale connection from pool")

            # Update pool metrics
            metrics = _get_metrics()
            if metrics:
                pool_info = self._pool.get_stats()
                metrics.db_pool_size.labels(state="idle").set(pool_info["pool_available"])
                metrics.db_pool_size.labels(state="active").set(
                    pool_info["pool_size"] - pool_info["pool_available"]
                )

            yield conn

        except psycopg.OperationalError as e:
            logger.error("Database operational error", error=str(e))
            # Connection is bad, close it when returning to pool
            if conn:
                self._pool.putconn(conn, close=True)
                conn = None

            # Increment failure metric
            metrics = _get_metrics()
            if metrics:
                metrics.db_pool_failures.inc()

            raise

        finally:
            # Return connection to pool (will be closed if marked)
            if conn:
                self._pool.putconn(conn)

    def write_aggregate(self, aggregate: TradeAggregate) -> None:
        """Write a single aggregate with idempotent upsert.

        Args:
            aggregate: The trade aggregate to write.

        Raises:
            psycopg.Error: If the database operation fails.
        """
        params = {
            "symbol": aggregate.symbol,
            "window_start": aggregate.window_start,
            "window_end": aggregate.window_end,
            "vwap": aggregate.vwap,
            "total_volume": aggregate.total_volume,
            "trade_count": aggregate.trade_count,
            "max_price": aggregate.max_price,
            "min_price": aggregate.min_price,
            "lmp": aggregate.lmp,
            "lmp_energy": aggregate.lmp_energy,
            "lmp_congestion": aggregate.lmp_congestion,
            "lmp_loss": aggregate.lmp_loss,
        }

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(self.UPSERT_AGGREGATE_SQL, params)
            conn.commit()

        logger.debug(
            "Wrote aggregate to database",
            symbol=aggregate.symbol,
            window_start=aggregate.window_start.isoformat(),
        )

    def write_aggregates_batch(self, aggregates: list[TradeAggregate]) -> int:
        """Write multiple aggregates in a single transaction with retry logic.

        Implements exponential backoff retry on OperationalError (network, DB restart, etc).
        After exhausting retries, logs error and continues (keep running).

        Args:
            aggregates: List of trade aggregates to write.

        Returns:
            Number of aggregates written, or 0 if all retries failed.
        """
        if not aggregates:
            return 0

        params_list = [
            {
                "symbol": agg.symbol,
                "window_start": agg.window_start,
                "window_end": agg.window_end,
                "vwap": agg.vwap,
                "total_volume": agg.total_volume,
                "trade_count": agg.trade_count,
                "max_price": agg.max_price,
                "min_price": agg.min_price,
                "lmp": agg.lmp,
                "lmp_energy": agg.lmp_energy,
                "lmp_congestion": agg.lmp_congestion,
                "lmp_loss": agg.lmp_loss,
            }
            for agg in aggregates
        ]

        # Retry loop with exponential backoff
        max_retries = self._settings.retry_max
        backoff_delays = self._settings.retry_backoff

        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.executemany(self.UPSERT_AGGREGATE_SQL, params_list)
                    conn.commit()

                # Success - record metric and return
                metrics = _get_metrics()
                if metrics and attempt > 0:
                    metrics.db_write_retries_total.labels(status="success").inc()

                logger.info(
                    "Wrote aggregate batch to database",
                    count=len(aggregates),
                    attempts=attempt + 1,
                )

                return len(aggregates)

            except psycopg.OperationalError as e:
                # Network error, DB restart, connection pool exhausted, etc
                is_last_attempt = attempt == max_retries - 1

                if is_last_attempt:
                    # Exhausted retries - log error, record failure metric, skip batch
                    metrics = _get_metrics()
                    if metrics:
                        metrics.db_write_retries_total.labels(status="failure").inc()

                    logger.error(
                        "DB write failed after all retries, skipping batch (keep running)",
                        count=len(aggregates),
                        attempts=attempt + 1,
                        error=str(e),
                    )

                    return 0  # Skip this batch, continue processing

                # Not last attempt - backoff and retry
                backoff = backoff_delays[min(attempt, len(backoff_delays) - 1)]
                logger.warning(
                    "DB write failed, retrying with backoff",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    backoff_seconds=backoff,
                    error=str(e),
                )

                time.sleep(backoff)

            except psycopg.Error as e:
                # Non-transient error (e.g., malformed SQL) - don't retry
                logger.error(
                    "DB write failed with non-transient error, skipping batch",
                    count=len(aggregates),
                    error_type=type(e).__name__,
                    error=str(e),
                )
                return 0

        # Should never reach here, but for safety
        return 0

    def write_dlq_record(self, dlq_message: DLQMessage) -> None:
        """Write a DLQ tracking record.

        Args:
            dlq_message: The DLQ message to record.
        """
        params = {
            "original_message": dlq_message.original_message,
            "error_type": dlq_message.error_type,
            "error_message": dlq_message.error_message,
            "failed_at": dlq_message.failed_at,
            "consumer_group": dlq_message.consumer_group,
            "partition": dlq_message.partition,
            "offset": dlq_message.offset,
        }

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(self.INSERT_DLQ_SQL, params)
            conn.commit()

        logger.debug("Wrote DLQ record to database")

    def check_connection(self) -> bool:
        """Check if database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False

    def get_latest_aggregates(
        self,
        symbol: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """Get the latest trade aggregates.

        Args:
            symbol: Filter by symbol (optional).
            limit: Maximum number of results.

        Returns:
            List of aggregate records as dictionaries.
        """
        sql = """
            SELECT symbol, window_start, window_end, vwap, total_volume,
                   trade_count, max_price, min_price,
                   lmp, lmp_energy, lmp_congestion, lmp_loss,
                   created_at, updated_at
            FROM trade_aggregates
        """
        params: dict[str, str | int] = {"limit": limit}

        if symbol:
            sql += " WHERE symbol = %(symbol)s"
            params["symbol"] = symbol

        sql += " ORDER BY window_start DESC LIMIT %(limit)s"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def query_all(
        self,
        sql: str,
        params: dict | None = None,
    ) -> list[dict[str, object]]:
        """Execute a SELECT query and return all rows.

        Public read interface intended for the API layer.
        Acquires a connection from the pool so concurrent calls are safe.
        Designed to be called via asyncio.to_thread() from async handlers.

        Args:
            sql: SQL query string with %(name)s placeholders.
            params: Query parameters.

        Returns:
            List of rows as dicts.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or {})
                return list(cur.fetchall())

    def close(self) -> None:
        """Close the database connection pool."""
        self._pool.close()
        logger.debug("Closed database connection pool")
