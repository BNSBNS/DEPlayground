"""Domain layer - core business logic.

This layer contains the business rules and domain models for ingestion.
It has NO dependencies on external frameworks or infrastructure.
"""

from ingestion.domain.models import (
    SourceType,
    SourceMetadata,
    RawEvent,
    EnrichedTradeEvent,
)

__all__ = [
    "SourceType",
    "SourceMetadata",
    "RawEvent",
    "EnrichedTradeEvent",
]
