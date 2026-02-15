"""Chain of Responsibility handlers for event processing.

Each handler processes the event and passes it to the next handler.
Handlers can:
- Transform the event
- Validate and reject the event
- Filter out events (return None)
- Raise exceptions for errors
"""

from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Any, Callable, Awaitable

import structlog

from src.ingestion.domain.models import EnrichedTradeEvent, RawEvent, SourceMetadata
from src.ingestion.domain.validators import (
    validate_symbol,
    validate_price,
    validate_volume,
    validate_timestamp,
    ValidationResult,
)
from src.ingestion.adapters.formats.base import DataAdapter


logger = structlog.get_logger()


class Handler(ABC):
    """Base handler in the Chain of Responsibility.

    Each handler processes an event and optionally passes it
    to the next handler in the chain.
    """

    def __init__(self, name: str | None = None):
        self._next: Handler | None = None
        self._name = name or self.__class__.__name__
        self._processed_count = 0
        self._filtered_count = 0
        self._error_count = 0

    @property
    def name(self) -> str:
        return self._name

    def set_next(self, handler: "Handler") -> "Handler":
        """Set the next handler in the chain.

        Args:
            handler: Next handler to process events

        Returns:
            The next handler (for fluent chaining)
        """
        self._next = handler
        return handler

    async def handle(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Handle an event and pass to next handler.

        Args:
            event: Event to process (raw dict or EnrichedTradeEvent)

        Returns:
            Processed event, or None if filtered out

        Raises:
            Exception: If processing fails
        """
        try:
            result = await self._process(event)

            if result is None:
                self._filtered_count += 1
                return None

            self._processed_count += 1

            # Pass to next handler if exists
            if self._next:
                return await self._next.handle(result)

            return result

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Handler error",
                handler=self._name,
                error=str(e),
            )
            raise

    @abstractmethod
    async def _process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Process the event.

        Args:
            event: Event to process

        Returns:
            Processed event, or None to filter out
        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get handler statistics."""
        return {
            "name": self._name,
            "processed_count": self._processed_count,
            "filtered_count": self._filtered_count,
            "error_count": self._error_count,
        }


class ValidationHandler(Handler):
    """Validate incoming events."""

    def __init__(
        self,
        strict: bool = True,
        max_future_seconds: int = 60,
        max_past_days: int = 7,
    ):
        """Initialize validation handler.

        Args:
            strict: If True, reject invalid events. If False, try to fix them.
            max_future_seconds: Maximum seconds in the future for timestamps
            max_past_days: Maximum days in the past for timestamps
        """
        super().__init__("ValidationHandler")
        self._strict = strict
        self._max_future_seconds = max_future_seconds
        self._max_past_days = max_past_days

    async def _process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Validate the event."""
        # If already an EnrichedTradeEvent, validate it
        if isinstance(event, EnrichedTradeEvent):
            return self._validate_enriched_event(event)

        # Raw dict - basic validation
        return self._validate_raw_event(event)

    def _validate_enriched_event(self, event: EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Validate an EnrichedTradeEvent."""
        errors = []

        # Validate symbol
        result = validate_symbol(event.symbol)
        if not result:
            errors.extend(result.errors)

        # Validate price
        result = validate_price(event.price)
        if not result:
            errors.extend(result.errors)

        # Validate volume
        result = validate_volume(event.volume)
        if not result:
            errors.extend(result.errors)

        # Validate timestamp
        result = validate_timestamp(
            event.event_timestamp,
            self._max_future_seconds,
            self._max_past_days,
        )
        if not result:
            errors.extend(result.errors)

        if errors:
            if self._strict:
                logger.warning(
                    "Event validation failed",
                    errors=errors,
                    symbol=event.symbol,
                )
                return None
            else:
                logger.debug("Event validation warnings", errors=errors)

        return event

    def _validate_raw_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Validate raw event dict."""
        required_fields = ["symbol", "price"]
        missing = [f for f in required_fields if f not in event]

        if missing:
            if self._strict:
                logger.warning("Missing required fields", missing=missing)
                return None

        # Pass through for further processing
        return event


class DeduplicationHandler(Handler):
    """Remove duplicate events based on idempotency key."""

    def __init__(
        self,
        cache_size: int = 100000,
        ttl_seconds: int = 3600,
    ):
        """Initialize deduplication handler.

        Args:
            cache_size: Maximum number of keys to cache
            ttl_seconds: Time-to-live for cached keys
        """
        super().__init__("DeduplicationHandler")
        self._cache: dict[str, float] = {}  # key -> timestamp
        self._cache_size = cache_size
        self._ttl_seconds = ttl_seconds
        self._duplicate_count = 0

    async def _process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Check for and filter duplicates."""
        if not isinstance(event, EnrichedTradeEvent):
            # Can't deduplicate raw events, pass through
            return event

        # Ensure idempotency key is computed
        if not event.idempotency_key:
            event.compute_idempotency_key()

        key = event.idempotency_key
        now = datetime.now(UTC).timestamp()

        # Clean expired entries
        self._cleanup_expired(now)

        # Check if duplicate
        if key in self._cache:
            self._duplicate_count += 1
            logger.debug("Duplicate event filtered", key=key)
            return None

        # Add to cache
        self._cache[key] = now

        # Evict oldest if cache is full
        if len(self._cache) > self._cache_size:
            oldest_key = min(self._cache, key=self._cache.get)
            del self._cache[oldest_key]

        return event

    def _cleanup_expired(self, now: float) -> None:
        """Remove expired entries from cache."""
        cutoff = now - self._ttl_seconds
        self._cache = {k: v for k, v in self._cache.items() if v > cutoff}

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        stats.update({
            "cache_size": len(self._cache),
            "max_cache_size": self._cache_size,
            "duplicate_count": self._duplicate_count,
        })
        return stats


class EnrichmentHandler(Handler):
    """Enrich events with metadata."""

    def __init__(self, source_metadata: SourceMetadata | None = None):
        """Initialize enrichment handler.

        Args:
            source_metadata: Default source metadata to add
        """
        super().__init__("EnrichmentHandler")
        self._source_metadata = source_metadata

    async def _process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Enrich the event with metadata."""
        if isinstance(event, EnrichedTradeEvent):
            # Add source metadata if not present
            if self._source_metadata and not event.source_metadata:
                event.source_metadata = self._source_metadata

            # Update processing timestamp
            event.processing_timestamp = datetime.now(UTC)

            # Compute idempotency key if not present
            if not event.idempotency_key:
                event.compute_idempotency_key()

            return event

        # Raw dict - pass through (transformation handler will convert)
        return event

    def set_source_metadata(self, metadata: SourceMetadata) -> None:
        """Update source metadata."""
        self._source_metadata = metadata


class TransformationHandler(Handler):
    """Transform raw data to EnrichedTradeEvent using an adapter."""

    def __init__(self, adapter: DataAdapter | None = None):
        """Initialize transformation handler.

        Args:
            adapter: Data adapter for format conversion
        """
        super().__init__("TransformationHandler")
        self._adapter = adapter

    async def _process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Transform raw event to EnrichedTradeEvent."""
        # Already transformed
        if isinstance(event, EnrichedTradeEvent):
            return event

        # No adapter — pass through unchanged for downstream handlers.
        # Adapter-less sources (batch, webhook, micro_batch) send events
        # that are either pre-canonical or validated by downstream handlers.
        if not self._adapter:
            return event

        # Transform using adapter
        events = self._adapter.safe_transform(event)

        # Return first event (handlers process one at a time)
        if events:
            return events[0]

        logger.debug("Adapter returned no events")
        return None

    def set_adapter(self, adapter: DataAdapter) -> None:
        """Set the data adapter."""
        self._adapter = adapter


class FilterHandler(Handler):
    """Filter events based on custom criteria."""

    def __init__(
        self,
        filter_func: Callable[[EnrichedTradeEvent], bool] | None = None,
        symbols: list[str] | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
    ):
        """Initialize filter handler.

        Args:
            filter_func: Custom filter function (returns True to keep)
            symbols: List of symbols to keep (None = all)
            min_price: Minimum price filter
            max_price: Maximum price filter
        """
        super().__init__("FilterHandler")
        self._filter_func = filter_func
        self._symbols = set(symbols) if symbols else None
        self._min_price = min_price
        self._max_price = max_price

    async def _process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Filter the event."""
        if not isinstance(event, EnrichedTradeEvent):
            return event  # Can only filter EnrichedTradeEvent

        # Custom filter
        if self._filter_func and not self._filter_func(event):
            return None

        # Symbol filter
        if self._symbols and event.symbol not in self._symbols:
            return None

        # Price filters
        if self._min_price and float(event.price) < self._min_price:
            return None

        if self._max_price and float(event.price) > self._max_price:
            return None

        return event
