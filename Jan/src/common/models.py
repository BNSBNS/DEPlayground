"""Pydantic models for trade events and aggregates.

This module defines the core data models used throughout the energy trading platform.
All models use strict validation to ensure data integrity in the trading pipeline.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TradeSide(str, Enum):
    """Trade direction - BUY or SELL."""

    BUY = "BUY"
    SELL = "SELL"


# Type aliases for trading precision
# NUMERIC(18,8) in PostgreSQL - supports up to 10 digits before decimal, 8 after
Price = Annotated[Decimal, Field(ge=Decimal("0"), decimal_places=8)]
Volume = Annotated[Decimal, Field(gt=Decimal("0"), decimal_places=8)]


class TradeEvent(BaseModel):
    """A single energy trade event.

    This model represents a trade captured from external APIs (EPEX, Nord Pool, etc.)
    and published to Kafka. The symbol field is used as the Kafka message key to
    ensure ordering guarantees per symbol within a partition.

    Attributes:
        trade_id: Unique identifier for the trade (UUID)
        symbol: Trading symbol (e.g., POWER_DE, GAS_NL, BRENT_OIL)
        price: Trade price with 8 decimal places precision
        volume: Trade volume (must be positive)
        side: Trade direction (BUY or SELL)
        trader_id: Identifier of the trader
        event_timestamp: UTC timestamp when the trade occurred (event time)
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    trade_id: UUID
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Z0-9_]+$")
    price: Decimal = Field(ge=Decimal("0"), decimal_places=8)
    volume: Decimal = Field(gt=Decimal("0"), decimal_places=8)
    side: TradeSide
    trader_id: str = Field(min_length=1, max_length=50)
    event_timestamp: datetime

    @field_validator("price", "volume", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: float | int | str | Decimal) -> Decimal:
        """Convert numeric values to Decimal for precise arithmetic."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("event_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Ensure timestamp is parsed correctly."""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    def to_kafka_key(self) -> bytes:
        """Get the Kafka message key (symbol) as bytes."""
        return self.symbol.encode("utf-8")

    def to_kafka_value(self) -> dict[str, str | float]:
        """Serialize to a Kafka-friendly dict with JSON-serializable types."""
        return {
            "trade_id": str(self.trade_id),
            "symbol": self.symbol,
            "price": str(self.price),
            "volume": str(self.volume),
            "side": self.side.value,
            "trader_id": self.trader_id,
            "event_timestamp": self.event_timestamp.isoformat(),
        }

    @classmethod
    def from_kafka_value(cls, data: dict[str, str | float]) -> "TradeEvent":
        """Deserialize from Kafka message value."""
        return cls(
            trade_id=UUID(str(data["trade_id"])),
            symbol=str(data["symbol"]),
            price=Decimal(str(data["price"])),
            volume=Decimal(str(data["volume"])),
            side=TradeSide(str(data["side"])),
            trader_id=str(data["trader_id"]),
            event_timestamp=datetime.fromisoformat(str(data["event_timestamp"])),
        )


class TradeAggregate(BaseModel):
    """Aggregated trade statistics for a time window.

    This model represents the output of windowed aggregation, containing
    metrics computed over a 1-minute tumbling window for a specific symbol.

    Attributes:
        symbol: Trading symbol
        window_start: Start timestamp of the aggregation window (UTC)
        window_end: End timestamp of the aggregation window (UTC)
        vwap: Volume Weighted Average Price
        total_volume: Sum of all trade volumes in the window
        trade_count: Number of trades in the window
        max_price: Maximum trade price in the window
        min_price: Minimum trade price in the window
        total_value: Sum of (price * volume) for VWAP calculation
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    symbol: str = Field(min_length=1, max_length=20)
    window_start: datetime
    window_end: datetime
    vwap: Decimal = Field(decimal_places=8)
    total_volume: Decimal = Field(ge=Decimal("0"), decimal_places=8)
    trade_count: int = Field(ge=0)
    max_price: Decimal = Field(ge=Decimal("0"), decimal_places=8)
    min_price: Decimal = Field(ge=Decimal("0"), decimal_places=8)
    total_value: Decimal = Field(ge=Decimal("0"), decimal_places=8)

    @field_validator("vwap", "total_volume", "max_price", "min_price", "total_value", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: float | int | str | Decimal) -> Decimal:
        """Convert numeric values to Decimal for precise arithmetic."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def to_db_tuple(self) -> tuple[str, datetime, datetime, Decimal, Decimal, int, Decimal, Decimal]:
        """Convert to a tuple for PostgreSQL insertion.

        Returns tuple matching the column order in trade_aggregates table:
        (symbol, window_start, window_end, vwap, total_volume, trade_count, max_price, min_price)
        """
        return (
            self.symbol,
            self.window_start,
            self.window_end,
            self.vwap,
            self.total_volume,
            self.trade_count,
            self.max_price,
            self.min_price,
        )


class DLQMessage(BaseModel):
    """Dead Letter Queue message wrapper.

    When a message cannot be processed (validation error, malformed JSON, etc.),
    it is wrapped in this model and sent to the DLQ topic for investigation.

    Attributes:
        original_message: The raw message that failed processing
        error_type: Type of error that occurred
        error_message: Human-readable error description
        failed_at: Timestamp when the failure occurred
        consumer_group: Consumer group that encountered the error
        partition: Kafka partition the message was read from
        offset: Kafka offset of the failed message
    """

    model_config = ConfigDict(extra="forbid")

    original_message: str
    error_type: str
    error_message: str
    failed_at: datetime
    consumer_group: str
    partition: int = Field(ge=0)
    offset: int = Field(ge=0)

    def to_kafka_value(self) -> dict[str, str | int]:
        """Serialize to a Kafka-friendly dict."""
        return {
            "original_message": self.original_message,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "failed_at": self.failed_at.isoformat(),
            "consumer_group": self.consumer_group,
            "partition": self.partition,
            "offset": self.offset,
        }
