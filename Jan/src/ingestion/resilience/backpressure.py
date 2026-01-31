"""Backpressure handling for streaming systems.

Manages situations where data is produced faster than it can be consumed.
"""

import asyncio
import random
from enum import Enum
from typing import TypeVar, Generic
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class BackpressureStrategy(str, Enum):
    """Strategies for handling backpressure."""

    BLOCK = "block"           # Block producer until space available
    DROP_OLDEST = "drop_oldest"  # Drop oldest events when full
    DROP_NEWEST = "drop_newest"  # Drop newest events when full
    SAMPLE = "sample"         # Statistically sample events


class BackpressureHandler(Generic[T]):
    """Handle backpressure in streaming systems.

    Example:
        ```python
        handler = BackpressureHandler[TradeEvent](
            max_buffer_size=10000,
            strategy=BackpressureStrategy.DROP_OLDEST
        )

        # Producer
        if await handler.push(event):
            print("Event buffered")
        else:
            print("Event dropped due to backpressure")

        # Consumer
        event = await handler.pop()
        process(event)
        ```
    """

    def __init__(
        self,
        max_buffer_size: int = 10000,
        strategy: BackpressureStrategy = BackpressureStrategy.BLOCK,
        sample_rate: float = 0.1,  # For SAMPLE strategy
        name: str = "default",
    ):
        """Initialize backpressure handler.

        Args:
            max_buffer_size: Maximum events to buffer
            strategy: How to handle full buffer
            sample_rate: Fraction of events to keep (for SAMPLE strategy)
            name: Identifier for logging
        """
        self.max_buffer_size = max_buffer_size
        self.strategy = strategy
        self.sample_rate = sample_rate
        self.name = name

        self._buffer: asyncio.Queue[T] = asyncio.Queue(maxsize=max_buffer_size)
        self._dropped_count = 0
        self._sampled_count = 0
        self._total_pushed = 0
        self._total_popped = 0

    @property
    def buffer_size(self) -> int:
        """Get current buffer size."""
        return self._buffer.qsize()

    @property
    def is_full(self) -> bool:
        """Check if buffer is full."""
        return self._buffer.full()

    @property
    def dropped_count(self) -> int:
        """Get number of dropped events."""
        return self._dropped_count

    async def push(self, item: T) -> bool:
        """Push item to buffer with backpressure handling.

        Args:
            item: Item to push

        Returns:
            True if item was buffered, False if dropped
        """
        self._total_pushed += 1

        if not self._buffer.full():
            await self._buffer.put(item)
            return True

        # Buffer is full - apply strategy
        match self.strategy:
            case BackpressureStrategy.BLOCK:
                # Block until space available
                await self._buffer.put(item)
                return True

            case BackpressureStrategy.DROP_OLDEST:
                # Remove oldest, add newest
                try:
                    self._buffer.get_nowait()
                    self._dropped_count += 1
                    await self._buffer.put(item)
                    logger.debug(
                        "Backpressure: dropped oldest",
                        handler=self.name,
                        buffer_size=self.buffer_size,
                    )
                    return True
                except asyncio.QueueEmpty:
                    await self._buffer.put(item)
                    return True

            case BackpressureStrategy.DROP_NEWEST:
                # Drop this item
                self._dropped_count += 1
                logger.debug(
                    "Backpressure: dropped newest",
                    handler=self.name,
                    buffer_size=self.buffer_size,
                )
                return False

            case BackpressureStrategy.SAMPLE:
                # Randomly decide whether to keep
                if random.random() < self.sample_rate:
                    try:
                        self._buffer.get_nowait()
                        self._dropped_count += 1
                    except asyncio.QueueEmpty:
                        pass
                    await self._buffer.put(item)
                    self._sampled_count += 1
                    return True
                else:
                    self._dropped_count += 1
                    return False

        return False

    def push_nowait(self, item: T) -> bool:
        """Push item without waiting.

        Args:
            item: Item to push

        Returns:
            True if item was buffered, False if dropped
        """
        self._total_pushed += 1

        try:
            self._buffer.put_nowait(item)
            return True
        except asyncio.QueueFull:
            if self.strategy == BackpressureStrategy.BLOCK:
                return False
            elif self.strategy == BackpressureStrategy.DROP_OLDEST:
                try:
                    self._buffer.get_nowait()
                    self._dropped_count += 1
                    self._buffer.put_nowait(item)
                    return True
                except asyncio.QueueEmpty:
                    return False
            else:
                self._dropped_count += 1
                return False

    async def pop(self, timeout: float | None = None) -> T:
        """Pop item from buffer.

        Args:
            timeout: Maximum seconds to wait (None = wait forever)

        Returns:
            Item from buffer

        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        if timeout is not None:
            item = await asyncio.wait_for(
                self._buffer.get(),
                timeout=timeout
            )
        else:
            item = await self._buffer.get()

        self._total_popped += 1
        return item

    def pop_nowait(self) -> T | None:
        """Pop item without waiting.

        Returns:
            Item from buffer, or None if empty
        """
        try:
            item = self._buffer.get_nowait()
            self._total_popped += 1
            return item
        except asyncio.QueueEmpty:
            return None

    async def drain(self, max_items: int | None = None) -> list[T]:
        """Drain multiple items from buffer.

        Args:
            max_items: Maximum items to drain (None = all available)

        Returns:
            List of items drained
        """
        items = []
        count = 0

        while True:
            if max_items is not None and count >= max_items:
                break

            item = self.pop_nowait()
            if item is None:
                break

            items.append(item)
            count += 1

        return items

    def get_stats(self) -> dict:
        """Get backpressure handler statistics."""
        return {
            "name": self.name,
            "strategy": self.strategy.value,
            "max_buffer_size": self.max_buffer_size,
            "current_size": self.buffer_size,
            "utilization_pct": (self.buffer_size / self.max_buffer_size) * 100,
            "total_pushed": self._total_pushed,
            "total_popped": self._total_popped,
            "dropped_count": self._dropped_count,
            "sampled_count": self._sampled_count,
            "drop_rate_pct": (
                (self._dropped_count / self._total_pushed * 100)
                if self._total_pushed > 0 else 0
            ),
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._dropped_count = 0
        self._sampled_count = 0
        self._total_pushed = 0
        self._total_popped = 0
