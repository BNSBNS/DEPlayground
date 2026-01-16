"""Unit tests for trade generator."""

from decimal import Decimal

import pytest

from src.common.models import TradeSide
from src.producer.trade_generator import SYMBOLS, TradeGenerator


class TestTradeGenerator:
    """Tests for TradeGenerator class."""

    def test_generator_initialization(self) -> None:
        """Test generator initialization with default symbols."""
        generator = TradeGenerator()
        assert len(generator.symbols) == len(SYMBOLS)

    def test_generator_with_custom_symbols(self) -> None:
        """Test generator with custom symbol list."""
        symbols = ["POWER_DE", "GAS_NL"]
        generator = TradeGenerator(symbols=symbols)
        assert generator.symbols == symbols

    def test_generator_with_seed(self) -> None:
        """Test generator produces reproducible results with seed."""
        gen1 = TradeGenerator(seed=42)
        gen2 = TradeGenerator(seed=42)

        trade1 = gen1.generate_trade()
        trade2 = gen2.generate_trade()

        # With same seed, should produce same symbol and side
        assert trade1.symbol == trade2.symbol
        assert trade1.side == trade2.side

    def test_generate_trade_has_required_fields(self) -> None:
        """Test that generated trade has all required fields."""
        generator = TradeGenerator(seed=42)
        trade = generator.generate_trade()

        assert trade.trade_id is not None
        assert trade.symbol in SYMBOLS
        assert trade.price >= Decimal("0")
        assert trade.volume > Decimal("0")
        assert trade.side in [TradeSide.BUY, TradeSide.SELL]
        assert trade.trader_id is not None
        assert trade.event_timestamp is not None

    def test_generate_trade_price_bounds(self) -> None:
        """Test that prices stay within expected bounds."""
        generator = TradeGenerator(symbols=["POWER_DE"], seed=42)

        base_price = SYMBOLS["POWER_DE"]["base_price"]
        min_expected = base_price * Decimal("0.8")  # type: ignore[operator]
        max_expected = base_price * Decimal("1.2")  # type: ignore[operator]

        for _ in range(100):
            trade = generator.generate_trade()
            assert min_expected <= trade.price <= max_expected

    def test_generate_trade_volume_positive(self) -> None:
        """Test that volume is always positive."""
        generator = TradeGenerator(seed=42)

        for _ in range(100):
            trade = generator.generate_trade()
            assert trade.volume >= Decimal("0.1")

    def test_generate_trades_iterator(self) -> None:
        """Test generating multiple trades via iterator."""
        generator = TradeGenerator(seed=42)
        trades = list(generator.generate_trades(10))

        assert len(trades) == 10
        for trade in trades:
            assert trade.symbol in SYMBOLS

    def test_burst_mode_higher_volume(self) -> None:
        """Test that burst mode tends to produce higher volumes."""
        generator = TradeGenerator(seed=42)

        normal_volumes = [generator.generate_trade(is_burst=False).volume for _ in range(50)]
        burst_volumes = [generator.generate_trade(is_burst=True).volume for _ in range(50)]

        avg_normal = sum(normal_volumes) / len(normal_volumes)
        avg_burst = sum(burst_volumes) / len(burst_volumes)

        # Burst volumes should be higher on average
        assert avg_burst > avg_normal

    def test_reset_prices(self) -> None:
        """Test price reset functionality."""
        generator = TradeGenerator(symbols=["POWER_DE"], seed=42)

        # Generate some trades to change prices
        for _ in range(10):
            generator.generate_trade()

        # Reset
        generator.reset_prices()

        # Prices should be back to base
        assert generator._current_prices["POWER_DE"] == SYMBOLS["POWER_DE"]["base_price"]

    def test_symbol_in_kafka_key(self) -> None:
        """Test that symbol is correctly used as Kafka key."""
        generator = TradeGenerator(symbols=["POWER_DE"], seed=42)
        trade = generator.generate_trade()

        assert trade.to_kafka_key() == b"POWER_DE"
