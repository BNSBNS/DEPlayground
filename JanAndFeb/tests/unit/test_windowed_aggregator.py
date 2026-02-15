"""Unit tests for windowed aggregator."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.common.models import TradeEvent, TradeSide
from src.consumer.windowed_aggregator import WindowedAggregator, WindowState


class TestWindowState:
    """Tests for WindowState class."""

    def test_empty_state(self) -> None:
        """Test empty window state."""
        state = WindowState()
        assert state.is_empty()
        assert state.trade_count == 0
        assert state.total_volume == Decimal("0")

    def test_add_single_trade(self) -> None:
        """Test adding a single trade to window."""
        state = WindowState()
        trade = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("100.00"),
            volume=Decimal("50.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime.now(UTC),
        )

        state.add_trade(trade)

        assert not state.is_empty()
        assert state.trade_count == 1
        assert state.total_volume == Decimal("50.00")
        assert state.max_price == Decimal("100.00")
        assert state.min_price == Decimal("100.00")

    def test_add_multiple_trades(self) -> None:
        """Test adding multiple trades to window."""
        state = WindowState()
        base_time = datetime.now(UTC)

        trades = [
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("100.00"),
                volume=Decimal("50.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_001",
                event_timestamp=base_time,
            ),
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("110.00"),
                volume=Decimal("30.00"),
                side=TradeSide.SELL,
                trader_id="TRADER_002",
                event_timestamp=base_time + timedelta(seconds=5),
            ),
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("95.00"),
                volume=Decimal("20.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_003",
                event_timestamp=base_time + timedelta(seconds=10),
            ),
        ]

        for trade in trades:
            state.add_trade(trade)

        assert state.trade_count == 3
        assert state.total_volume == Decimal("100.00")
        assert state.max_price == Decimal("110.00")
        assert state.min_price == Decimal("95.00")

    def test_vwap_calculation(self) -> None:
        """Test VWAP calculation."""
        state = WindowState()
        base_time = datetime.now(UTC)

        # Trade 1: price=100, volume=60 -> value=6000
        # Trade 2: price=110, volume=40 -> value=4400
        # Total value: 10400, Total volume: 100
        # VWAP = 10400 / 100 = 104

        trades = [
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("100.00"),
                volume=Decimal("60.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_001",
                event_timestamp=base_time,
            ),
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("110.00"),
                volume=Decimal("40.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_002",
                event_timestamp=base_time + timedelta(seconds=5),
            ),
        ]

        for trade in trades:
            state.add_trade(trade)

        vwap = state.compute_vwap()
        assert vwap == Decimal("104.00000000")

    def test_vwap_empty_window(self) -> None:
        """Test VWAP calculation for empty window."""
        state = WindowState()
        assert state.compute_vwap() == Decimal("0")


class TestWindowedAggregator:
    """Tests for WindowedAggregator class."""

    def test_aggregator_initialization(self) -> None:
        """Test aggregator initialization."""
        aggregator = WindowedAggregator(
            window_duration_seconds=60,
            late_event_grace_seconds=30,
        )
        assert aggregator.get_active_window_count() == 0

    def test_add_single_trade(self) -> None:
        """Test adding a single trade creates a window."""
        aggregator = WindowedAggregator(window_duration_seconds=60)
        trade = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("100.00"),
            volume=Decimal("50.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime(2026, 1, 17, 10, 0, 30, tzinfo=UTC),
        )

        completed = aggregator.add_trade(trade)

        assert aggregator.get_active_window_count() == 1
        assert len(completed) == 0  # Window not complete yet

    def test_window_alignment(self) -> None:
        """Test that windows are aligned to minute boundaries."""
        aggregator = WindowedAggregator(window_duration_seconds=60)

        # Trade at 10:00:45 should be in window starting at 10:00:00
        trade = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("100.00"),
            volume=Decimal("50.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime(2026, 1, 17, 10, 0, 45, tzinfo=UTC),
        )

        aggregator.add_trade(trade)

        state = aggregator.get_state_summary()
        assert state["active_windows"] == 1

    def test_multiple_symbols_separate_windows(
        self,
        multiple_symbol_trades: list[TradeEvent],
    ) -> None:
        """Test that different symbols create separate windows."""
        aggregator = WindowedAggregator(window_duration_seconds=60)

        for trade in multiple_symbol_trades:
            aggregator.add_trade(trade)

        # Should have 3 windows (one per symbol)
        assert aggregator.get_active_window_count() == 3

    def test_window_completion(self) -> None:
        """Test that windows complete after grace period."""
        aggregator = WindowedAggregator(
            window_duration_seconds=60,
            late_event_grace_seconds=30,
        )

        # Add trade in first minute
        trade1 = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("100.00"),
            volume=Decimal("50.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime(2026, 1, 17, 10, 0, 30, tzinfo=UTC),
        )
        aggregator.add_trade(trade1)

        # Add trade 2 minutes later (past grace period)
        trade2 = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("105.00"),
            volume=Decimal("60.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime(2026, 1, 17, 10, 2, 30, tzinfo=UTC),
        )
        completed = aggregator.add_trade(trade2)

        # First window should be completed (returns WindowFlushResult wrapping TradeAggregate)
        assert len(completed) == 1
        assert completed[0].aggregate.symbol == "POWER_DE"
        assert completed[0].aggregate.trade_count == 1
        assert completed[0].aggregate.total_volume == Decimal("50.00")

    def test_flush_all(self) -> None:
        """Test flushing all windows."""
        aggregator = WindowedAggregator(window_duration_seconds=60)

        # Add trades for multiple symbols
        base_time = datetime(2026, 1, 17, 10, 0, 30, tzinfo=UTC)
        symbols = ["POWER_DE", "GAS_NL"]

        for i, symbol in enumerate(symbols):
            trade = TradeEvent(
                trade_id=uuid4(),
                symbol=symbol,
                price=Decimal("100.00"),
                volume=Decimal("50.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_001",
                event_timestamp=base_time + timedelta(seconds=i),
            )
            aggregator.add_trade(trade)

        # Flush all
        completed = aggregator.flush_all()

        assert len(completed) == 2
        assert aggregator.get_active_window_count() == 0

    def test_aggregate_values(self, sample_trades: list[TradeEvent]) -> None:
        """Test that aggregate values are computed correctly."""
        aggregator = WindowedAggregator(
            window_duration_seconds=60,
            late_event_grace_seconds=0,  # No grace period for testing
        )

        # Add all trades (all in same window)
        for trade in sample_trades:
            aggregator.add_trade(trade)

        # Flush to get aggregate
        completed = aggregator.flush_all()

        assert len(completed) == 1
        agg = completed[0].aggregate  # WindowFlushResult wraps TradeAggregate

        assert agg.symbol == "POWER_DE"
        assert agg.trade_count == 10

        # Verify total volume
        expected_volume = sum(t.volume for t in sample_trades)
        assert agg.total_volume == expected_volume

        # Verify max/min prices
        expected_max = max(t.price for t in sample_trades)
        expected_min = min(t.price for t in sample_trades)
        assert agg.max_price == expected_max
        assert agg.min_price == expected_min
