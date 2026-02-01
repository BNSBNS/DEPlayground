"""CQRS Projections - Update read models from events.

Projections consume domain events and update read-optimized models.
They transform event-sourced data into queryable views.

This is the "Q" side of CQRS:
- Events come from Kafka (trades-events topic)
- Projections update denormalized read models
- Read models are optimized for specific query patterns

Example flow:
    TradeAggregatedEvent → VWAPProjection → VWAPSummaryReadModel (in PostgreSQL)
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Generic, TypeVar

import structlog

from src.cqrs.events import DomainEvent, TradeAggregatedEvent, TradeSubmittedEvent
from src.cqrs.read_models import SymbolActivityReadModel, VWAPSummaryReadModel

logger = structlog.get_logger(__name__)

E = TypeVar("E", bound=DomainEvent)
M = TypeVar("M")


class Projection(ABC, Generic[E, M]):
    """Base class for projections.

    A projection:
    1. Subscribes to specific event types
    2. Maintains read model state
    3. Handles events to update the read model

    Projections should be idempotent - processing the same event
    twice should not corrupt the read model.
    """

    @property
    @abstractmethod
    def event_types(self) -> list[type[DomainEvent]]:
        """Event types this projection handles."""
        pass

    @abstractmethod
    def handle(self, event: E) -> M | None:
        """Handle an event and return updated read model.

        Args:
            event: Domain event to process

        Returns:
            Updated read model or None if no update needed
        """
        pass

    def can_handle(self, event: DomainEvent) -> bool:
        """Check if this projection handles the event type."""
        return type(event) in self.event_types


class VWAPProjection(Projection[TradeAggregatedEvent, VWAPSummaryReadModel]):
    """Projects TradeAggregatedEvents into VWAP summary read model.

    This projection maintains real-time VWAP summaries per symbol:
    - Current VWAP (latest window)
    - 1-hour VWAP (rolling)
    - 24-hour VWAP (rolling)
    - Volume statistics

    The read model is optimized for dashboard queries like:
    "Show me current VWAP for all symbols"
    """

    def __init__(self):
        """Initialize the projection."""
        # In-memory cache of read models (in production, this would be in DB)
        self._models: dict[str, VWAPSummaryReadModel] = {}

    @property
    def event_types(self) -> list[type[DomainEvent]]:
        """Event types this projection handles."""
        return [TradeAggregatedEvent]

    def handle(self, event: TradeAggregatedEvent) -> VWAPSummaryReadModel:
        """Update VWAP summary from aggregate event.

        Args:
            event: Trade aggregation event

        Returns:
            Updated VWAPSummaryReadModel
        """
        symbol = event.symbol

        # Get or create read model
        if symbol in self._models:
            model = self._models[symbol]
        else:
            model = VWAPSummaryReadModel(symbol=symbol)

        # Update current VWAP
        model.current_vwap = event.vwap
        model.last_updated = event.window_end

        # Update rolling averages (simplified - in production use windowed aggregates)
        # This is a simplification; real implementation would use time-windowed storage
        if model.vwap_1h is None:
            model.vwap_1h = event.vwap
        else:
            # Simple exponential moving average (decay factor ~0.97 for 60 windows = 1 hour)
            model.vwap_1h = model.vwap_1h * Decimal("0.97") + event.vwap * Decimal("0.03")

        if model.vwap_24h is None:
            model.vwap_24h = event.vwap
        else:
            # Slower decay for 24-hour
            model.vwap_24h = model.vwap_24h * Decimal("0.9996") + event.vwap * Decimal("0.0004")

        # Update volume
        if model.total_volume_24h is None:
            model.total_volume_24h = event.total_volume
        else:
            model.total_volume_24h += event.total_volume

        # Update trade count
        if model.trade_count_24h is None:
            model.trade_count_24h = event.trade_count
        else:
            model.trade_count_24h += event.trade_count

        # Update LMP if available
        if event.lmp is not None:
            model.current_lmp = event.lmp

        # Store updated model
        self._models[symbol] = model

        logger.debug(
            "VWAP projection updated",
            symbol=symbol,
            current_vwap=str(model.current_vwap),
            vwap_1h=str(model.vwap_1h),
        )

        return model

    def get_model(self, symbol: str) -> VWAPSummaryReadModel | None:
        """Get current read model for a symbol."""
        return self._models.get(symbol)

    def get_all_models(self) -> list[VWAPSummaryReadModel]:
        """Get all read models."""
        return list(self._models.values())


class SymbolActivityProjection(Projection[TradeSubmittedEvent, SymbolActivityReadModel]):
    """Projects TradeSubmittedEvents into symbol activity read model.

    This projection tracks trading activity per symbol:
    - Last trade time
    - Trades in last minute
    - Average trade size
    - Active status

    Useful for "Which symbols are actively trading?" queries.
    """

    def __init__(self):
        """Initialize the projection."""
        self._models: dict[str, SymbolActivityReadModel] = {}
        self._recent_trades: dict[str, list[datetime]] = {}

    @property
    def event_types(self) -> list[type[DomainEvent]]:
        """Event types this projection handles."""
        return [TradeSubmittedEvent]

    def handle(self, event: TradeSubmittedEvent) -> SymbolActivityReadModel:
        """Update symbol activity from trade event.

        Args:
            event: Trade submitted event

        Returns:
            Updated SymbolActivityReadModel
        """
        symbol = event.symbol
        now = datetime.now(UTC)

        # Get or create model
        if symbol in self._models:
            model = self._models[symbol]
        else:
            model = SymbolActivityReadModel(symbol=symbol)
            self._recent_trades[symbol] = []

        # Update last trade time
        model.last_trade_time = event.event_timestamp

        # Track recent trades for per-minute count
        self._recent_trades[symbol].append(event.event_timestamp)

        # Clean old trades (keep last minute only)
        cutoff = now - timedelta(minutes=1) if 'timedelta' in dir() else now
        from datetime import timedelta
        cutoff = now - timedelta(minutes=1)
        self._recent_trades[symbol] = [
            t for t in self._recent_trades[symbol]
            if t > cutoff
        ]
        model.trades_last_minute = len(self._recent_trades[symbol])

        # Update average trade size (simple running average)
        if model.avg_trade_size is None:
            model.avg_trade_size = event.volume
        else:
            model.avg_trade_size = (model.avg_trade_size + event.volume) / 2

        # Update active status (active if traded in last 5 minutes)
        model.is_active = (now - event.event_timestamp).total_seconds() < 300

        self._models[symbol] = model
        return model

    def get_model(self, symbol: str) -> SymbolActivityReadModel | None:
        """Get current activity model for a symbol."""
        return self._models.get(symbol)

    def get_active_symbols(self) -> list[str]:
        """Get list of currently active symbols."""
        return [s for s, m in self._models.items() if m.is_active]


class ProjectionManager:
    """Manages multiple projections and routes events to them.

    The ProjectionManager:
    1. Maintains a registry of projections
    2. Routes events to appropriate projections
    3. Provides access to read models

    Example:
        >>> manager = ProjectionManager()
        >>> manager.register(VWAPProjection())
        >>> manager.register(SymbolActivityProjection())
        >>> manager.process_event(event)
    """

    def __init__(self):
        """Initialize the projection manager."""
        self._projections: list[Projection] = []

    def register(self, projection: Projection) -> None:
        """Register a projection.

        Args:
            projection: Projection instance to register
        """
        self._projections.append(projection)
        logger.info(
            "Registered projection",
            projection=projection.__class__.__name__,
            event_types=[et.__name__ for et in projection.event_types],
        )

    def process_event(self, event: DomainEvent) -> list:
        """Process an event through all applicable projections.

        Args:
            event: Domain event to process

        Returns:
            List of updated read models
        """
        results = []
        for projection in self._projections:
            if projection.can_handle(event):
                try:
                    result = projection.handle(event)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(
                        "Projection failed",
                        projection=projection.__class__.__name__,
                        event_type=type(event).__name__,
                        error=str(e),
                    )
        return results

    def get_projection(self, projection_type: type[Projection]) -> Projection | None:
        """Get a registered projection by type."""
        for p in self._projections:
            if isinstance(p, projection_type):
                return p
        return None
