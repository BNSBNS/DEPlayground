"""Pipeline builder for constructing handler chains.

Provides a fluent API for building processing pipelines.
"""

from typing import Any, Callable

from src.ingestion.pipeline.handlers import (
    Handler,
    ValidationHandler,
    DeduplicationHandler,
    EnrichmentHandler,
    TransformationHandler,
    FilterHandler,
)
from src.ingestion.domain.models import EnrichedTradeEvent, SourceMetadata
from src.ingestion.adapters.formats.base import DataAdapter


class PipelineBuilder:
    """Builder for constructing event processing pipelines.

    Example:
        ```python
        pipeline = (
            PipelineBuilder()
            .add_validation(strict=True)
            .add_transformation(adapter=FinnhubAdapter())
            .add_enrichment(source_metadata=metadata)
            .add_deduplication(cache_size=10000)
            .add_filter(symbols=["STOCK_AAPL", "CRYPTO_BTC"])
            .build()
        )

        result = await pipeline.handle(raw_event)
        ```
    """

    def __init__(self):
        self._handlers: list[Handler] = []

    def add_handler(self, handler: Handler) -> "PipelineBuilder":
        """Add a custom handler to the pipeline.

        Args:
            handler: Handler to add

        Returns:
            Self for fluent chaining
        """
        self._handlers.append(handler)
        return self

    def add_validation(
        self,
        strict: bool = True,
        max_future_seconds: int = 60,
        max_past_days: int = 7,
    ) -> "PipelineBuilder":
        """Add validation handler.

        Args:
            strict: Reject invalid events if True
            max_future_seconds: Max seconds in future for timestamps
            max_past_days: Max days in past for timestamps

        Returns:
            Self for fluent chaining
        """
        handler = ValidationHandler(
            strict=strict,
            max_future_seconds=max_future_seconds,
            max_past_days=max_past_days,
        )
        return self.add_handler(handler)

    def add_deduplication(
        self,
        cache_size: int = 100000,
        ttl_seconds: int = 3600,
    ) -> "PipelineBuilder":
        """Add deduplication handler.

        Args:
            cache_size: Maximum keys to cache
            ttl_seconds: Time-to-live for cached keys

        Returns:
            Self for fluent chaining
        """
        handler = DeduplicationHandler(
            cache_size=cache_size,
            ttl_seconds=ttl_seconds,
        )
        return self.add_handler(handler)

    def add_enrichment(
        self,
        source_metadata: SourceMetadata | None = None,
    ) -> "PipelineBuilder":
        """Add enrichment handler.

        Args:
            source_metadata: Default metadata to add

        Returns:
            Self for fluent chaining
        """
        handler = EnrichmentHandler(source_metadata=source_metadata)
        return self.add_handler(handler)

    def add_transformation(
        self,
        adapter: DataAdapter | None = None,
    ) -> "PipelineBuilder":
        """Add transformation handler.

        Args:
            adapter: Data adapter for format conversion

        Returns:
            Self for fluent chaining
        """
        handler = TransformationHandler(adapter=adapter)
        return self.add_handler(handler)

    def add_filter(
        self,
        filter_func: Callable[[EnrichedTradeEvent], bool] | None = None,
        symbols: list[str] | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> "PipelineBuilder":
        """Add filter handler.

        Args:
            filter_func: Custom filter function
            symbols: Symbols to keep
            min_price: Minimum price filter
            max_price: Maximum price filter

        Returns:
            Self for fluent chaining
        """
        handler = FilterHandler(
            filter_func=filter_func,
            symbols=symbols,
            min_price=min_price,
            max_price=max_price,
        )
        return self.add_handler(handler)

    def build(self) -> Handler:
        """Build the pipeline.

        Returns:
            First handler in the chain

        Raises:
            ValueError: If no handlers added
        """
        if not self._handlers:
            raise ValueError("Pipeline must have at least one handler")

        # Chain handlers together
        for i in range(len(self._handlers) - 1):
            self._handlers[i].set_next(self._handlers[i + 1])

        return self._handlers[0]

    def build_default(self, adapter: DataAdapter | None = None) -> Handler:
        """Build a default pipeline with common handlers.

        Default chain: Validation -> Transformation -> Enrichment -> Deduplication

        Args:
            adapter: Optional data adapter

        Returns:
            First handler in the chain
        """
        return (
            PipelineBuilder()
            .add_validation(strict=True)
            .add_transformation(adapter=adapter)
            .add_enrichment()
            .add_deduplication()
            .build()
        )


class Pipeline:
    """Wrapper for a handler chain with statistics."""

    def __init__(self, head: Handler):
        """Initialize pipeline.

        Args:
            head: First handler in the chain
        """
        self._head = head
        self._processed_count = 0
        self._error_count = 0

    async def process(self, event: dict[str, Any] | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Process an event through the pipeline.

        Args:
            event: Event to process

        Returns:
            Processed event or None if filtered
        """
        try:
            result = await self._head.handle(event)
            if result:
                self._processed_count += 1
            return result
        except Exception:
            self._error_count += 1
            raise

    async def process_batch(
        self,
        events: list[dict[str, Any] | EnrichedTradeEvent],
    ) -> list[EnrichedTradeEvent]:
        """Process a batch of events.

        Args:
            events: Events to process

        Returns:
            List of successfully processed events
        """
        results = []
        for event in events:
            try:
                result = await self.process(event)
                if result:
                    results.append(result)
            except Exception:
                continue  # Log and skip errors
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        stats = {
            "processed_count": self._processed_count,
            "error_count": self._error_count,
            "handlers": [],
        }

        # Collect stats from all handlers
        handler = self._head
        while handler:
            stats["handlers"].append(handler.get_stats())
            handler = handler._next

        return stats
