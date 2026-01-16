"""Integration tests for database writer.

These tests require a running PostgreSQL instance.
Run with: pytest tests/integration -v

To skip if no database available:
    pytest tests/integration -v -m "not requires_db"
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.common.models import TradeAggregate
from src.consumer.db_writer import DatabaseWriter

# Skip all tests if no database URL provided
pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_DSN"),
    reason="POSTGRES_DSN environment variable not set",
)


class TestDatabaseWriter:
    """Integration tests for DatabaseWriter."""

    @pytest.fixture
    def db_writer(self) -> DatabaseWriter:
        """Create database writer with test DSN."""
        return DatabaseWriter()

    @pytest.fixture
    def sample_aggregate(self) -> TradeAggregate:
        """Create a sample aggregate for testing."""
        return TradeAggregate(
            symbol="TEST_SYMBOL",
            window_start=datetime(2026, 1, 17, 10, 0, 0, tzinfo=UTC),
            window_end=datetime(2026, 1, 17, 10, 1, 0, tzinfo=UTC),
            vwap=Decimal("100.50000000"),
            total_volume=Decimal("1000.00000000"),
            trade_count=50,
            max_price=Decimal("105.00000000"),
            min_price=Decimal("96.00000000"),
            total_value=Decimal("100500.00000000"),
        )

    def test_connection_check(self, db_writer: DatabaseWriter) -> None:
        """Test database connection health check."""
        assert db_writer.check_connection() is True

    def test_write_single_aggregate(
        self,
        db_writer: DatabaseWriter,
        sample_aggregate: TradeAggregate,
    ) -> None:
        """Test writing a single aggregate."""
        db_writer.write_aggregate(sample_aggregate)

        # Verify it was written
        results = db_writer.get_latest_aggregates(
            symbol=sample_aggregate.symbol,
            limit=1,
        )

        assert len(results) >= 1
        assert results[0]["symbol"] == sample_aggregate.symbol

    def test_idempotent_upsert(
        self,
        db_writer: DatabaseWriter,
        sample_aggregate: TradeAggregate,
    ) -> None:
        """Test that duplicate writes are handled idempotently."""
        # Write same aggregate twice
        db_writer.write_aggregate(sample_aggregate)
        db_writer.write_aggregate(sample_aggregate)

        # Should only have one record for this window
        results = db_writer.get_latest_aggregates(
            symbol=sample_aggregate.symbol,
            limit=10,
        )

        # Filter for our specific window
        matching = [
            r for r in results
            if r["window_start"] == sample_aggregate.window_start
        ]
        assert len(matching) == 1

    def test_write_batch(self, db_writer: DatabaseWriter) -> None:
        """Test writing a batch of aggregates."""
        base_time = datetime(2026, 1, 17, 11, 0, 0, tzinfo=UTC)
        aggregates = []

        for i in range(5):
            aggregates.append(
                TradeAggregate(
                    symbol="BATCH_TEST",
                    window_start=base_time + timedelta(minutes=i),
                    window_end=base_time + timedelta(minutes=i + 1),
                    vwap=Decimal("100.00"),
                    total_volume=Decimal("100.00"),
                    trade_count=10,
                    max_price=Decimal("105.00"),
                    min_price=Decimal("95.00"),
                    total_value=Decimal("10000.00"),
                )
            )

        written = db_writer.write_aggregates_batch(aggregates)
        assert written == 5

    def test_close_connection(self, db_writer: DatabaseWriter) -> None:
        """Test closing database connection."""
        # Verify connection works
        assert db_writer.check_connection() is True

        # Close
        db_writer.close()

        # Connection should be closed (check_connection will reconnect)
        # This just verifies close() doesn't raise
