"""Secondary port for event publishing.

This port defines how the ingestion system publishes processed events
to downstream systems (Kafka, databases, etc.).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ingestion.domain.models import EnrichedTradeEvent


class EventPublisherPort(ABC):
    """Secondary port - defines how data leaves the system.

    This is the driven side of the hexagonal architecture.
    Implementations include Kafka publishers, database writers, etc.
    """

    @abstractmethod
    async def publish(self, event: "EnrichedTradeEvent") -> None:
        """Publish a single event.

        Args:
            event: The enriched trade event to publish

        Raises:
            PublishError: If the event cannot be published
        """
        ...

    @abstractmethod
    async def publish_batch(self, events: list["EnrichedTradeEvent"]) -> None:
        """Publish a batch of events.

        More efficient than publishing events one by one.

        Args:
            events: List of enriched trade events to publish

        Raises:
            PublishError: If events cannot be published
        """
        ...

    @abstractmethod
    async def flush(self) -> None:
        """Flush any buffered events.

        Ensures all pending events are delivered before returning.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the publisher is healthy.

        Returns:
            True if the publisher can accept events, False otherwise
        """
        ...


class PublishError(Exception):
    """Raised when event publishing fails."""

    def __init__(self, message: str, event: "EnrichedTradeEvent | None" = None):
        super().__init__(message)
        self.event = event
