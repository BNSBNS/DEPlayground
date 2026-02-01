"""CQRS Domain Events - Facts about what happened.

Domain events represent facts that have occurred in the system. They are:
- Immutable (facts don't change)
- Named in past tense (TradeSubmitted, not SubmitTrade)
- Published to Kafka for downstream consumers

Events are used for:
1. Updating read models (projections)
2. Triggering side effects (notifications, analytics)
3. Event sourcing (reconstructing state from events)
4. Integration with other systems

Event flow: Command Handler → Domain Event → Kafka → Projection Handlers
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Base class for all domain events.

    Domain events are immutable records of something that happened.
    They should contain all information needed to:
    - Understand what happened
    - Update read models
    - Replay the system state

    Attributes:
        event_id: Unique identifier for this event
        event_type: Type name of the event (for deserialization)
        occurred_at: When the event occurred
        aggregate_id: ID of the aggregate that produced this event
        aggregate_type: Type of the aggregate
        version: Event version for schema evolution
        correlation_id: ID to correlate related events
        causation_id: ID of the event/command that caused this event
    """

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(default="")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: str = Field(default="")
    aggregate_type: str = Field(default="")
    version: int = Field(default=1)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None

    def __init__(self, **data):
        """Initialize with auto-set event_type."""
        if "event_type" not in data:
            data["event_type"] = self.__class__.__name__
        super().__init__(**data)

    def to_kafka_value(self) -> dict[str, Any]:
        """Serialize to Kafka message value."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "version": self.version,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "payload": self._get_payload(),
        }

    def _get_payload(self) -> dict[str, Any]:
        """Get event-specific payload (override in subclasses)."""
        return {}

    def to_kafka_key(self) -> bytes:
        """Get Kafka message key (typically aggregate_id)."""
        return self.aggregate_id.encode("utf-8")


class TradeSubmittedEvent(DomainEvent):
    """Event: A trade was submitted to the system.

    This event is published when a trade passes validation and is
    accepted for processing. It contains all trade details.

    Downstream consumers can use this to:
    - Update real-time dashboards
    - Trigger risk calculations
    - Feed analytics pipelines
    """

    aggregate_type: str = Field(default="Trade")

    # Trade details
    trade_id: UUID
    symbol: str
    price: Decimal
    volume: Decimal
    side: str  # BUY or SELL
    trader_id: str
    event_timestamp: datetime
    source: str = "unknown"

    def _get_payload(self) -> dict[str, Any]:
        """Get trade-specific payload."""
        return {
            "trade_id": str(self.trade_id),
            "symbol": self.symbol,
            "price": str(self.price),
            "volume": str(self.volume),
            "side": self.side,
            "trader_id": self.trader_id,
            "event_timestamp": self.event_timestamp.isoformat(),
            "source": self.source,
        }


class TradeAggregatedEvent(DomainEvent):
    """Event: A window of trades was aggregated.

    This event is published when a time window closes and aggregates
    are computed. It contains the VWAP and other metrics.

    Downstream consumers can use this to:
    - Update read models for fast queries
    - Feed BI tools (Superset, PowerBI)
    - Trigger alerts on price movements
    """

    aggregate_type: str = Field(default="TradeAggregate")

    # Aggregate details
    symbol: str
    window_start: datetime
    window_end: datetime
    vwap: Decimal
    total_volume: Decimal
    trade_count: int
    max_price: Decimal
    min_price: Decimal

    # LMP components (if calculated)
    lmp: Decimal | None = None
    lmp_energy: Decimal | None = None
    lmp_congestion: Decimal | None = None
    lmp_loss: Decimal | None = None

    def _get_payload(self) -> dict[str, Any]:
        """Get aggregate-specific payload."""
        payload = {
            "symbol": self.symbol,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "vwap": str(self.vwap),
            "total_volume": str(self.total_volume),
            "trade_count": self.trade_count,
            "max_price": str(self.max_price),
            "min_price": str(self.min_price),
        }

        # Include LMP if available
        if self.lmp is not None:
            payload.update({
                "lmp": str(self.lmp),
                "lmp_energy": str(self.lmp_energy) if self.lmp_energy else None,
                "lmp_congestion": str(self.lmp_congestion) if self.lmp_congestion else None,
                "lmp_loss": str(self.lmp_loss) if self.lmp_loss else None,
            })

        return payload


class DataQualityEvent(DomainEvent):
    """Event: A data quality check was performed.

    This event tracks data quality metrics over time, useful for:
    - Quality trend analysis
    - Alerting on quality degradation
    - Audit trails
    """

    aggregate_type: str = Field(default="DataQuality")

    source: str
    symbol: str
    quality_score: float
    issues_count: int
    check_types: list[str] = Field(default_factory=list)

    def _get_payload(self) -> dict[str, Any]:
        """Get quality-specific payload."""
        return {
            "source": self.source,
            "symbol": self.symbol,
            "quality_score": self.quality_score,
            "issues_count": self.issues_count,
            "check_types": self.check_types,
        }


# Event type registry for deserialization
EVENT_TYPES: dict[str, type[DomainEvent]] = {
    "TradeSubmittedEvent": TradeSubmittedEvent,
    "TradeAggregatedEvent": TradeAggregatedEvent,
    "DataQualityEvent": DataQualityEvent,
}


def deserialize_event(data: dict[str, Any]) -> DomainEvent:
    """Deserialize a domain event from dictionary.

    Args:
        data: Event data including event_type and payload

    Returns:
        Deserialized domain event

    Raises:
        ValueError: If event_type is unknown
    """
    event_type = data.get("event_type")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type}")

    event_class = EVENT_TYPES[event_type]
    payload = data.get("payload", {})

    # Merge base fields with payload
    event_data = {
        "event_id": UUID(data["event_id"]),
        "event_type": event_type,
        "occurred_at": datetime.fromisoformat(data["occurred_at"]),
        "aggregate_id": data["aggregate_id"],
        "aggregate_type": data.get("aggregate_type", ""),
        "version": data.get("version", 1),
        **payload,
    }

    if data.get("correlation_id"):
        event_data["correlation_id"] = UUID(data["correlation_id"])
    if data.get("causation_id"):
        event_data["causation_id"] = UUID(data["causation_id"])

    # Convert string decimals back to Decimal
    decimal_fields = ["price", "volume", "vwap", "total_volume", "max_price", "min_price",
                      "lmp", "lmp_energy", "lmp_congestion", "lmp_loss"]
    for field in decimal_fields:
        if field in event_data and event_data[field] is not None:
            event_data[field] = Decimal(str(event_data[field]))

    # Convert string UUIDs to UUID
    if "trade_id" in event_data:
        event_data["trade_id"] = UUID(event_data["trade_id"])

    # Convert string datetimes
    datetime_fields = ["event_timestamp", "window_start", "window_end"]
    for field in datetime_fields:
        if field in event_data and isinstance(event_data[field], str):
            event_data[field] = datetime.fromisoformat(event_data[field])

    return event_class(**event_data)
