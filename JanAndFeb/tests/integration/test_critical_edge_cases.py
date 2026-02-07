"""Integration tests for critical edge cases and data loss prevention.

Tests cover the fixes for:
1. Window eviction data loss (Issue #1)
2. DLQ payload preservation (Issue #2)
3. Backpressure memory coordination (Issue #4)
4. Safe shutdown with flush (Issue #6)
"""

import asyncio
import json
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, MagicMock

import pytest

from src.common.models import TradeEvent, TradeSide
from src.consumer.windowed_aggregator import WindowedAggregator, WindowFlushResult
from src.consumer.backpressure import BackpressureController, FlowState
from src.ingestion.domain.models import EnrichedTradeEvent, SourceMetadata, SourceType


class TestWindowEviction:
    """Test that evicted windows are properly written to database.

    Covers Issue #1: Window eviction data loss
    """

    def test_evicted_windows_are_returned(self):
        """Test that evicted windows are included in results."""
        # Create aggregator with very low max_windows limit
        aggregator = WindowedAggregator(
            window_duration_seconds=60,
            max_windows=5,  # Very low to trigger eviction quickly
        )

        # Add trades to create many windows (more than max_windows)
        base_time = datetime.now(UTC)
        results_with_evicted = []

        # Create 10 different windows (exceeds max_windows=5)
        for i in range(10):
            window_time = base_time + timedelta(minutes=i)
            trade = TradeEvent(
                symbol=f"SYMBOL_{i}",
                price=Decimal("100.0"),
                volume=Decimal("10.0"),
                side=TradeSide.BUY,
                trader_id="test",
                event_timestamp=window_time,
            )

            results = aggregator.add_trade(trade, partition=0, offset=i)
            results_with_evicted.extend(results)

        # Should have evicted windows in results
        assert len(results_with_evicted) > 0, "Evicted windows should be returned"

        # Verify evicted windows have valid data
        for result in results_with_evicted:
            assert isinstance(result, WindowFlushResult)
            assert result.aggregate.trade_count > 0
            assert result.aggregate.vwap > 0
            assert len(result.partition_offsets) > 0

    def test_evicted_windows_preserve_offsets(self):
        """Test that evicted windows track Kafka offsets correctly."""
        aggregator = WindowedAggregator(max_windows=3)

        base_time = datetime.now(UTC)

        # Create windows with specific offsets
        for i in range(5):
            window_time = base_time + timedelta(minutes=i)
            trade = TradeEvent(
                symbol=f"SYM{i}",
                price=Decimal("50.0"),
                volume=Decimal("5.0"),
                side=TradeSide.SELL,
                trader_id="trader1",
                event_timestamp=window_time,
            )

            results = aggregator.add_trade(trade, partition=0, offset=100 + i)

            # Check that evicted results have offset info
            for result in results:
                assert 0 in result.partition_offsets
                assert result.partition_offsets[0] >= 100


class TestDLQPayloadPreservation:
    """Test that DLQ preserves original payload and error context.

    Covers Issue #2: DLQ payload loss
    """

    @pytest.mark.asyncio
    async def test_dlq_preserves_original_payload(self):
        """Test that DLQ event contains original raw data."""
        from src.ingestion.manager import IngestionManager

        # Mock publisher
        mock_publisher = AsyncMock()

        manager = IngestionManager(
            publisher=mock_publisher,
            dlq_publisher=mock_publisher,
        )

        # Simulate failed event
        raw_event = {
            "symbol": "AAPL",
            "price": "invalid_price",  # Will cause error
            "volume": 100,
        }

        error = ValueError("Invalid price format")

        # Send to DLQ
        await manager._send_to_dlq(raw_event, error, "test_source")

        # Verify DLQ publisher was called
        assert mock_publisher.publish.called

        # Get the DLQ event that was published
        dlq_event = mock_publisher.publish.call_args[0][0]

        # Verify original payload is preserved
        assert dlq_event.dlq_original_payload is not None
        payload_dict = json.loads(dlq_event.dlq_original_payload)
        assert payload_dict["symbol"] == "AAPL"
        assert payload_dict["price"] == "invalid_price"

        # Verify error context is preserved
        assert dlq_event.dlq_error_type == "ValueError"
        assert "Invalid price format" in dlq_event.dlq_error_message

        # Verify symbol is extracted
        assert "AAPL" in dlq_event.symbol

    @pytest.mark.asyncio
    async def test_dlq_handles_non_serializable_payload(self):
        """Test DLQ handles payloads that can't be JSON serialized."""
        from src.ingestion.manager import IngestionManager

        mock_publisher = AsyncMock()
        manager = IngestionManager(
            publisher=mock_publisher,
            dlq_publisher=mock_publisher,
        )

        # Non-serializable object
        class CustomObject:
            pass

        raw_event = CustomObject()
        error = TypeError("Cannot serialize")

        # Should not crash
        await manager._send_to_dlq(raw_event, error, "test_source")

        assert mock_publisher.publish.called
        dlq_event = mock_publisher.publish.call_args[0][0]

        # Should store string representation
        assert dlq_event.dlq_original_payload is not None
        assert "CustomObject" in dlq_event.dlq_original_payload


class TestBackpressureMemoryCoordination:
    """Test that backpressure coordinates with aggregator memory state.

    Covers Issue #4: Backpressure doesn't coordinate with memory
    """

    def test_backpressure_pauses_on_memory_pressure(self):
        """Test that backpressure triggers when memory is high."""
        mock_consumer = Mock()
        mock_consumer.assignment.return_value = []

        # Memory check that returns high usage
        def memory_check_high():
            return (800 * 1024 * 1024, 1000 * 1024 * 1024)  # 80% usage

        controller = BackpressureController(
            mock_consumer,
            high_watermark=1000,
            low_watermark=100,
            memory_check_fn=memory_check_high,
        )

        # Even with low message count, should pause on memory
        controller.on_message_received()
        controller.on_message_completed()

        # Trigger check
        controller._check_backpressure()

        # Should be paused due to memory pressure
        assert controller.state == FlowState.PAUSED
        assert controller._memory_pause_count > 0

    def test_backpressure_resumes_when_memory_clears(self):
        """Test that backpressure resumes when memory drops."""
        mock_consumer = Mock()
        mock_consumer.assignment.return_value = []

        # Start with high memory
        memory_state = {"current": 800 * 1024 * 1024}

        def memory_check():
            return (memory_state["current"], 1000 * 1024 * 1024)

        controller = BackpressureController(
            mock_consumer,
            high_watermark=1000,
            low_watermark=100,
            memory_check_fn=memory_check,
        )

        # Trigger pause
        controller._check_backpressure()
        assert controller.state == FlowState.PAUSED

        # Clear memory pressure
        memory_state["current"] = 100 * 1024 * 1024  # 10% usage

        # Should resume
        controller._check_backpressure()
        assert controller.state == FlowState.FLOWING

    def test_backpressure_tracks_memory_stats(self):
        """Test that memory pause count is tracked."""
        mock_consumer = Mock()
        mock_consumer.assignment.return_value = []

        def memory_check_high():
            return (900 * 1024 * 1024, 1000 * 1024 * 1024)

        controller = BackpressureController(
            mock_consumer,
            memory_check_fn=memory_check_high,
        )

        # Trigger multiple memory pauses
        for _ in range(3):
            controller._state = FlowState.FLOWING  # Reset state
            controller._check_backpressure()

        stats = controller.get_stats()
        assert "memory_pause_count" in stats
        assert stats["memory_pause_count"] >= 1


class TestSafeShutdown:
    """Test safe shutdown with complete flush.

    Covers Issue #6: Testing gaps - shutdown scenarios
    """

    def test_flush_all_returns_incomplete_windows(self):
        """Test that flush_all returns all windows, even incomplete ones."""
        aggregator = WindowedAggregator(
            window_duration_seconds=60,
            late_event_grace_seconds=30,
        )

        # Add trades to windows that haven't closed yet
        base_time = datetime.now(UTC)

        for i in range(3):
            trade = TradeEvent(
                symbol="SYMBOL",
                price=Decimal("100.0"),
                volume=Decimal(f"{i+1}.0"),
                side=TradeSide.BUY,
                trader_id="trader1",
                event_timestamp=base_time + timedelta(seconds=i * 10),
            )
            aggregator.add_trade(trade, partition=0, offset=i)

        # Windows should not be closed yet (within same minute)
        assert aggregator.get_active_window_count() > 0

        # Flush all
        results = aggregator.flush_all()

        # Should return the incomplete windows
        assert len(results) > 0
        assert all(isinstance(r, WindowFlushResult) for r in results)

        # Should have aggregated all 3 trades
        total_trades = sum(r.aggregate.trade_count for r in results)
        assert total_trades == 3

        # Aggregator should be empty after flush
        assert aggregator.get_active_window_count() == 0

    def test_flush_all_preserves_offsets(self):
        """Test that flush_all preserves Kafka offset tracking."""
        aggregator = WindowedAggregator()

        base_time = datetime.now(UTC)
        trade = TradeEvent(
            symbol="TEST",
            price=Decimal("50.0"),
            volume=Decimal("10.0"),
            side=TradeSide.SELL,
            trader_id="trader2",
            event_timestamp=base_time,
        )

        # Add trade with specific offset
        aggregator.add_trade(trade, partition=1, offset=999)

        # Flush
        results = aggregator.flush_all()

        # Should have offset info
        assert len(results) == 1
        assert 1 in results[0].partition_offsets
        assert results[0].partition_offsets[1] == 999


class TestIntegrationScenarios:
    """Integration scenarios combining multiple components."""

    def test_high_cardinality_with_eviction(self):
        """Test system behavior with many unique symbols (high cardinality)."""
        aggregator = WindowedAggregator(
            window_duration_seconds=60,
            max_windows=100,  # Limit to force eviction
        )

        base_time = datetime.now(UTC)
        evicted_count = 0

        # Create 200 unique symbol-window combinations
        for i in range(200):
            symbol = f"SYMBOL_{i % 50}"  # 50 unique symbols
            window_time = base_time + timedelta(minutes=i // 50)

            trade = TradeEvent(
                symbol=symbol,
                price=Decimal("100.0"),
                volume=Decimal("1.0"),
                side=TradeSide.BUY,
                trader_id="trader",
                event_timestamp=window_time,
            )

            results = aggregator.add_trade(trade)
            evicted_count += len(results)

        # Should have evicted some windows
        assert evicted_count > 0

        # Active windows should be capped at max_windows
        assert aggregator.get_active_window_count() <= 100

    def test_future_dated_events_with_memory_backpressure(self):
        """Test handling of future-dated events causing memory growth."""
        mock_consumer = Mock()
        mock_consumer.assignment.return_value = []

        aggregator = WindowedAggregator(
            max_windows=50,
            max_memory_mb=10,  # Very low limit
        )

        # Memory check function
        def check_memory():
            return (
                aggregator.get_estimated_memory_usage(),
                aggregator.max_memory_bytes,
            )

        controller = BackpressureController(
            mock_consumer,
            high_watermark=1000,
            low_watermark=100,
            memory_check_fn=check_memory,
        )

        base_time = datetime.now(UTC)

        # Add many future-dated events (different windows)
        for i in range(100):
            future_time = base_time + timedelta(minutes=i)
            trade = TradeEvent(
                symbol="FUTURE",
                price=Decimal("100.0"),
                volume=Decimal("1.0"),
                side=TradeSide.BUY,
                trader_id="trader",
                event_timestamp=future_time,
            )

            aggregator.add_trade(trade)
            controller.on_message_received()
            controller.on_message_completed()

        # Should have triggered memory-based backpressure
        stats = controller.get_stats()
        assert stats["memory_pause_count"] > 0 or controller.state == FlowState.PAUSED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
