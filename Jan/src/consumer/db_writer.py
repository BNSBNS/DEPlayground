"""PostgreSQL database writer with idempotent upserts.

This module provides a database writer that ensures idempotent writes
using INSERT ... ON CONFLICT for at-least-once streaming semantics.
"""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from src.common.config import PostgresSettings, get_settings
from src.common.logging_config import get_logger
from src.common.models import DLQMessage, TradeAggregate

logger = get_logger(__name__)


class DatabaseWriter:
    """PostgreSQL writer with idempotent upsert semantics.

    Uses INSERT ... ON CONFLICT to handle duplicate writes that may occur
    during consumer restarts or reprocessing. This ensures correctness
    with at-least-once delivery semantics.
    """

    # SQL for idempotent upsert of trade aggregates
    UPSERT_AGGREGATE_SQL = """
        INSERT INTO trade_aggregates (
            symbol, window_start, window_end, vwap, total_volume,
            trade_count, max_price, min_price, created_at, updated_at
        )
        VALUES (
            %(symbol)s, %(window_start)s, %(window_end)s, %(vwap)s, %(total_volume)s,
            %(trade_count)s, %(max_price)s, %(min_price)s, NOW(), NOW()
        )
        ON CONFLICT (symbol, window_start) DO UPDATE SET
            vwap = EXCLUDED.vwap,
            total_volume = EXCLUDED.total_volume,
            trade_count = EXCLUDED.trade_count,
            max_price = EXCLUDED.max_price,
            min_price = EXCLUDED.min_price,
            window_end = EXCLUDED.window_end,
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
        *,
        pool_size: int = 5,
    ) -> None:
        """Initialize the database writer.

        Args:
            settings: PostgreSQL connection settings.
            pool_size: Connection pool size.
        """
        if settings is None:
            settings = get_settings().postgres

        self._dsn = settings.get_dsn()
        self._pool_size = pool_size
        self._conn: psycopg.Connection[dict[str, object]] | None = None

        logger.info(
            "Database writer initialized",
            host=settings.host,
            database=settings.db,
        )

    @contextmanager
    def _get_connection(self) -> Iterator[psycopg.Connection[dict[str, object]]]:
        """Get a database connection.

        In production, this would use a connection pool.
        For simplicity, we use a single connection with reconnect logic.
        """
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                self._dsn,
                row_factory=dict_row,
                autocommit=False,
            )
            logger.debug("Created new database connection")

        try:
            yield self._conn
        except psycopg.OperationalError as e:
            logger.error("Database connection error", error=str(e))
            if self._conn and not self._conn.closed:
                self._conn.close()
            self._conn = None
            raise

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
        """Write multiple aggregates in a single transaction.

        Args:
            aggregates: List of trade aggregates to write.

        Returns:
            Number of aggregates written.

        Raises:
            psycopg.Error: If the database operation fails.
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
            }
            for agg in aggregates
        ]

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(self.UPSERT_AGGREGATE_SQL, params_list)
            conn.commit()

        logger.info(
            "Wrote aggregate batch to database",
            count=len(aggregates),
        )

        return len(aggregates)

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
                   trade_count, max_price, min_price, created_at, updated_at
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

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.debug("Closed database connection")
