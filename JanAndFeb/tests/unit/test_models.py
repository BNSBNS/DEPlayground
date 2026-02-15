"""Unit tests for Pydantic models."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.common.models import DLQMessage, TradeAggregate, TradeEvent, TradeSide


class TestTradeEvent:
    """Tests for TradeEvent model."""

    def test_valid_trade_event(self) -> None:
        """Test creating a valid trade event."""
        trade = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("85.50"),
            volume=Decimal("100.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime.now(UTC),
        )

        assert trade.symbol == "POWER_DE"
        assert trade.price == Decimal("85.50")
        assert trade.volume == Decimal("100.00")
        assert trade.side == TradeSide.BUY

    def test_price_from_float(self) -> None:
        """Test that float prices are converted to Decimal."""
        trade = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=85.50,  # type: ignore[arg-type]
            volume=100.00,  # type: ignore[arg-type]
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp=datetime.now(UTC),
        )

        assert isinstance(trade.price, Decimal)
        assert trade.price == Decimal("85.5")

    def test_negative_price_rejected(self) -> None:
        """Test that negative prices are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("-10.00"),
                volume=Decimal("100.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_001",
                event_timestamp=datetime.now(UTC),
            )

        assert "price" in str(exc_info.value)

    def test_zero_volume_rejected(self) -> None:
        """Test that zero volume is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TradeEvent(
                trade_id=uuid4(),
                symbol="POWER_DE",
                price=Decimal("85.50"),
                volume=Decimal("0"),
                side=TradeSide.BUY,
                trader_id="TRADER_001",
                event_timestamp=datetime.now(UTC),
            )

        assert "volume" in str(exc_info.value)

    def test_invalid_symbol_rejected(self) -> None:
        """Test that invalid symbols are rejected."""
        with pytest.raises(ValidationError):
            TradeEvent(
                trade_id=uuid4(),
                symbol="invalid-symbol!",  # Contains invalid characters
                price=Decimal("85.50"),
                volume=Decimal("100.00"),
                side=TradeSide.BUY,
                trader_id="TRADER_001",
                event_timestamp=datetime.now(UTC),
            )

    def test_to_kafka_key(self, sample_trade: TradeEvent) -> None:
        """Test Kafka key generation."""
        key = sample_trade.to_kafka_key()
        assert isinstance(key, bytes)
        assert key == b"POWER_DE"

    def test_to_kafka_value(self, sample_trade: TradeEvent) -> None:
        """Test Kafka value serialization."""
        value = sample_trade.to_kafka_value()

        assert isinstance(value, dict)
        assert value["symbol"] == "POWER_DE"
        assert value["side"] == "BUY"
        assert "trade_id" in value
        assert "event_timestamp" in value

    def test_from_kafka_value_roundtrip(self, sample_trade: TradeEvent) -> None:
        """Test serialization and deserialization roundtrip."""
        kafka_value = sample_trade.to_kafka_value()
        restored = TradeEvent.from_kafka_value(kafka_value)

        assert restored.trade_id == sample_trade.trade_id
        assert restored.symbol == sample_trade.symbol
        assert restored.price == sample_trade.price
        assert restored.volume == sample_trade.volume
        assert restored.side == sample_trade.side

    def test_timestamp_parsing(self) -> None:
        """Test ISO timestamp parsing."""
        trade = TradeEvent(
            trade_id=uuid4(),
            symbol="POWER_DE",
            price=Decimal("85.50"),
            volume=Decimal("100.00"),
            side=TradeSide.BUY,
            trader_id="TRADER_001",
            event_timestamp="2026-01-17T10:30:00Z",  # type: ignore[arg-type]
        )

        assert trade.event_timestamp.year == 2026
        assert trade.event_timestamp.month == 1
        assert trade.event_timestamp.day == 17


class TestTradeAggregate:
    """Tests for TradeAggregate model."""

    def test_valid_aggregate(self, sample_aggregate: TradeAggregate) -> None:
        """Test creating a valid trade aggregate."""
        assert sample_aggregate.symbol == "POWER_DE"
        assert sample_aggregate.vwap == Decimal("87.25000000")
        assert sample_aggregate.trade_count == 10

    def test_to_db_tuple(self, sample_aggregate: TradeAggregate) -> None:
        """Test database tuple conversion."""
        db_tuple = sample_aggregate.to_db_tuple()

        assert len(db_tuple) == 12  # 8 original + 4 LMP fields
        assert db_tuple[0] == "POWER_DE"  # symbol
        assert db_tuple[4] == sample_aggregate.total_volume
        # LMP fields default to None
        assert db_tuple[8] is None   # lmp
        assert db_tuple[9] is None   # lmp_energy
        assert db_tuple[10] is None  # lmp_congestion
        assert db_tuple[11] is None  # lmp_loss


class TestDLQMessage:
    """Tests for DLQMessage model."""

    def test_valid_dlq_message(self) -> None:
        """Test creating a valid DLQ message."""
        dlq = DLQMessage(
            original_message='{"invalid": "json',
            error_type="JSONDecodeError",
            error_message="Expecting property name",
            failed_at=datetime.now(UTC),
            consumer_group="trade-aggregator",
            partition=0,
            offset=12345,
        )

        assert dlq.error_type == "JSONDecodeError"
        assert dlq.partition == 0
        assert dlq.offset == 12345

    def test_to_kafka_value(self) -> None:
        """Test Kafka value serialization for DLQ."""
        dlq = DLQMessage(
            original_message="test message",
            error_type="ValidationError",
            error_message="Invalid field",
            failed_at=datetime.now(UTC),
            consumer_group="trade-aggregator",
            partition=2,
            offset=999,
        )

        value = dlq.to_kafka_value()
        assert value["partition"] == 2
        assert value["offset"] == 999
        assert value["error_type"] == "ValidationError"
