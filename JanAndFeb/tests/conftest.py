"""Pytest configuration and shared fixtures."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.common.models import TradeAggregate, TradeEvent, TradeSide


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run E2E tests (requires Docker stack to be running)",
    )


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "e2e: End-to-end tests requiring Docker stack")


@pytest.fixture
def sample_trade() -> TradeEvent:
    """Create a sample trade event for testing."""
    return TradeEvent(
        trade_id=uuid4(),
        symbol="POWER_DE",
        price=Decimal("85.50"),
        volume=Decimal("100.00"),
        side=TradeSide.BUY,
        trader_id="TRADER_001",
        event_timestamp=datetime.now(UTC),
    )


@pytest.fixture
def sample_trades() -> list[TradeEvent]:
    """Create multiple sample trade events."""
    base_time = datetime(2026, 1, 17, 10, 0, 0, tzinfo=UTC)
    trades = []

    for i in range(10):
        trades.append(
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("85.00") + Decimal(str(i * 0.5)),
                volume=Decimal("100.00") + Decimal(str(i * 10)),
                side=TradeSide.BUY if i % 2 == 0 else TradeSide.SELL,
                trader_id=f"TRADER_{i:03d}",
                event_timestamp=base_time + timedelta(seconds=i * 5),
            )
        )

    return trades


@pytest.fixture
def sample_aggregate() -> TradeAggregate:
    """Create a sample trade aggregate for testing."""
    window_start = datetime(2026, 1, 17, 10, 0, 0, tzinfo=UTC)
    return TradeAggregate(
        symbol="POWER_DE",
        window_start=window_start,
        window_end=window_start + timedelta(minutes=1),
        vwap=Decimal("87.25000000"),
        total_volume=Decimal("1450.00000000"),
        trade_count=10,
        max_price=Decimal("89.50000000"),
        min_price=Decimal("85.00000000"),
        total_value=Decimal("126512.50000000"),
    )


@pytest.fixture
def multiple_symbol_trades() -> list[TradeEvent]:
    """Create trades for multiple symbols."""
    base_time = datetime(2026, 1, 17, 10, 0, 0, tzinfo=UTC)
    symbols = ["POWER_DE", "POWER_FR", "GAS_NL"]
    trades = []

    for i, symbol in enumerate(symbols):
        for j in range(5):
            trades.append(
                TradeEvent(
                    trade_id=uuid4(),
                    symbol=symbol,
                    price=Decimal("80.00") + Decimal(str(i * 5 + j)),
                    volume=Decimal("50.00") + Decimal(str(j * 10)),
                    side=TradeSide.BUY,
                    trader_id="TRADER_001",
                    event_timestamp=base_time + timedelta(seconds=j * 10),
                )
            )

    return trades
