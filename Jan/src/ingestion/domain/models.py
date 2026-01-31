"""Domain models for the ingestion system.

These models represent the core domain concepts and are independent
of any external infrastructure (Kafka, databases, APIs).

Medallion Architecture Layers:
- Bronze: RawEvent (exactly as received from source)
- Silver: EnrichedTradeEvent (validated, deduplicated, normalized)
- Gold: TradeAggregate (pre-computed in consumer, stored in TimescaleDB)
"""

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceType(str, Enum):
    """Data source type classification.

    Each type has different latency characteristics and connection patterns.
    """

    WEBSOCKET = "websocket"      # Real-time bidirectional (~20-170ms)
    SSE = "sse"                  # Server-sent events (~100-500ms)
    POLLING = "polling"          # Periodic REST calls (configurable interval)
    WEBHOOK = "webhook"          # Push notifications (event-driven)
    MICRO_BATCH = "micro_batch"  # Windowed batches (5-30s)
    BATCH = "batch"              # Historical/bulk imports (hourly/daily)
    SYNTHETIC = "synthetic"      # Internal generator (for testing)


class SourceMetadata(BaseModel):
    """Metadata about the data source.

    Tracks provenance and latency information for each event.
    This enables analytics on data freshness and source reliability.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    source_type: SourceType
    source_name: str = Field(
        min_length=1,
        max_length=50,
        description="Human-readable source identifier (e.g., 'finnhub', 'entsoe')",
    )
    ingestion_timestamp: datetime = Field(
        description="When the event was received by our system (UTC)",
    )
    expected_latency_ms: int = Field(
        ge=0,
        description="Expected latency from source to our system in milliseconds",
    )
    batch_id: str | None = Field(
        default=None,
        max_length=100,
        description="Batch identifier for batch/micro-batch sources",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts for this event",
    )

    @field_validator("ingestion_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Ensure timestamp is in UTC."""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        else:
            dt = v
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for Kafka."""
        return {
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "ingestion_timestamp": self.ingestion_timestamp.isoformat(),
            "expected_latency_ms": self.expected_latency_ms,
            "batch_id": self.batch_id,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceMetadata":
        """Deserialize from dictionary."""
        return cls(
            source_type=SourceType(data["source_type"]),
            source_name=data["source_name"],
            ingestion_timestamp=datetime.fromisoformat(data["ingestion_timestamp"]),
            expected_latency_ms=data["expected_latency_ms"],
            batch_id=data.get("batch_id"),
            retry_count=data.get("retry_count", 0),
        )


class RawEvent(BaseModel):
    """Raw event from Bronze layer - exactly as received from source.

    This is the unprocessed event data. It preserves the original format
    for debugging and replay purposes.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",  # Allow extra fields from various sources
    )

    raw_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the raw event",
    )
    source_metadata: SourceMetadata
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event was received",
    )
    raw_data: dict[str, Any] = Field(
        description="Original event data from the source",
    )

    def to_kafka_value(self) -> dict[str, Any]:
        """Serialize for Kafka (Bronze layer topic)."""
        return {
            "raw_id": str(self.raw_id),
            "source_metadata": self.source_metadata.to_dict(),
            "received_at": self.received_at.isoformat(),
            "raw_data": self.raw_data,
        }


class TradeSide(str, Enum):
    """Trade direction."""

    BUY = "BUY"
    SELL = "SELL"


class EnrichedTradeEvent(BaseModel):
    """Enriched trade event for Silver layer - validated and normalized.

    This extends the base TradeEvent with source metadata while maintaining
    backward compatibility with existing consumers.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    # Core trade fields (same as TradeEvent)
    trade_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the trade",
    )
    symbol: str = Field(
        min_length=1,
        max_length=20,
        pattern=r"^[A-Z0-9_]+$",
        description="Trading symbol (e.g., POWER_DE, STOCK_AAPL)",
    )
    price: Decimal = Field(
        ge=Decimal("0"),
        decimal_places=8,
        description="Trade price with 8 decimal precision",
    )
    volume: Decimal = Field(
        gt=Decimal("0"),
        decimal_places=8,
        description="Trade volume (must be positive)",
    )
    side: TradeSide = Field(
        description="Trade direction (BUY or SELL)",
    )
    trader_id: str = Field(
        min_length=1,
        max_length=50,
        description="Identifier of the trader or source",
    )
    event_timestamp: datetime = Field(
        description="When the trade occurred (event time, UTC)",
    )

    # Enrichment fields (new)
    source_metadata: SourceMetadata | None = Field(
        default=None,
        description="Source provenance and latency information",
    )
    processing_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event was processed by ingestion",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=64,
        description="Deterministic key for deduplication",
    )

    @field_validator("price", "volume", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: float | int | str | Decimal) -> Decimal:
        """Convert numeric values to Decimal."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("event_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Ensure timestamp is in UTC."""
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        else:
            dt = v
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    def to_kafka_key(self) -> bytes:
        """Get Kafka message key (symbol for partition ordering)."""
        return self.symbol.encode("utf-8")

    def to_kafka_value(self) -> dict[str, Any]:
        """Serialize to Kafka-friendly dict.

        Maintains backward compatibility with existing consumers:
        - Base fields are always present
        - source_metadata is optional and can be ignored by old consumers
        """
        value = {
            "trade_id": str(self.trade_id),
            "symbol": self.symbol,
            "price": str(self.price),
            "volume": str(self.volume),
            "side": self.side.value,
            "trader_id": self.trader_id,
            "event_timestamp": self.event_timestamp.isoformat(),
        }

        # Add enrichment fields
        if self.source_metadata:
            value["source_metadata"] = self.source_metadata.to_dict()
        value["processing_timestamp"] = self.processing_timestamp.isoformat()
        if self.idempotency_key:
            value["idempotency_key"] = self.idempotency_key

        return value

    @classmethod
    def from_kafka_value(cls, data: dict[str, Any]) -> "EnrichedTradeEvent":
        """Deserialize from Kafka message."""
        source_metadata = None
        if "source_metadata" in data and data["source_metadata"]:
            source_metadata = SourceMetadata.from_dict(data["source_metadata"])

        return cls(
            trade_id=UUID(str(data["trade_id"])),
            symbol=str(data["symbol"]),
            price=Decimal(str(data["price"])),
            volume=Decimal(str(data["volume"])),
            side=TradeSide(str(data["side"])),
            trader_id=str(data["trader_id"]),
            event_timestamp=datetime.fromisoformat(str(data["event_timestamp"])),
            source_metadata=source_metadata,
            processing_timestamp=datetime.fromisoformat(
                data.get("processing_timestamp", datetime.now(UTC).isoformat())
            ),
            idempotency_key=data.get("idempotency_key"),
        )

    def compute_idempotency_key(self) -> str:
        """Compute deterministic idempotency key for deduplication.

        Uses a hash of key event properties to detect duplicates.
        """
        import hashlib

        components = [
            self.symbol,
            str(self.price),
            str(self.volume),
            self.event_timestamp.isoformat(),
            self.trader_id,
        ]
        key = hashlib.sha256("|".join(components).encode()).hexdigest()[:32]
        self.idempotency_key = key
        return key

    def calculate_latency_ms(self) -> float | None:
        """Calculate ingestion latency in milliseconds.

        Returns:
            Latency from event_timestamp to processing_timestamp, or None
        """
        if self.processing_timestamp and self.event_timestamp:
            delta = self.processing_timestamp - self.event_timestamp
            return delta.total_seconds() * 1000
        return None
