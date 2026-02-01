"""CQRS (Command Query Responsibility Segregation) module.

This module implements CQRS pattern for the Energy Trading Platform:
- Commands: Actions that change state (submit trade, cancel trade)
- Events: Facts about what happened (trade submitted, trade aggregated)
- Queries: Read-optimized models for serving data

The current architecture already has natural CQRS separation:
- Command side: Producer/Ingestion → Kafka → Consumer (writes to DB)
- Query side: API → PostgreSQL (reads from DB)

This module adds explicit domain events and read model projections.

For a full event-sourcing implementation, see docs/EVENT_SOURCING.md
"""

from src.cqrs.commands import Command, CommandBus, SubmitTradeCommand
from src.cqrs.events import (
    DomainEvent,
    TradeAggregatedEvent,
    TradeSubmittedEvent,
)
from src.cqrs.projections import Projection, VWAPProjection
from src.cqrs.read_models import SymbolActivityReadModel, VWAPSummaryReadModel

__all__ = [
    # Commands
    "Command",
    "CommandBus",
    "SubmitTradeCommand",
    # Events
    "DomainEvent",
    "TradeSubmittedEvent",
    "TradeAggregatedEvent",
    # Projections
    "Projection",
    "VWAPProjection",
    # Read Models
    "VWAPSummaryReadModel",
    "SymbolActivityReadModel",
]
