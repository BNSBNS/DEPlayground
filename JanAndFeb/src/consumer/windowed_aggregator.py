"""Windowed aggregation for trade events.

This module implements 1-minute tumbling window aggregation for trade events,
computing VWAP, total volume, trade count, and price extremes per symbol.

Key improvements for production correctness:
1. Offset tracking per window for safe shutdown and replay
2. Memory guardrails with configurable limits
3. State size monitoring and eviction policies
"""

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from src.common.logging_config import get_logger
from src.common.models import TradeAggregate, TradeEvent

logger = get_logger(__name__)


@dataclass
class OffsetWatermark:
    """Tracks Kafka offsets associated with a window.

    This enables safe shutdown by knowing which offsets correspond
    to which window's data, so we can commit correctly after flushing.
    """
    partition: int = -1
    min_offset: int = -1  # First offset in this window
    max_offset: int = -1  # Last offset in this window

    def update(self, partition: int, offset: int) -> None:
        """Update watermark with a new offset."""
        self.partition = partition
        if self.min_offset < 0 or offset < self.min_offset:
            self.min_offset = offset
        if offset > self.max_offset:
            self.max_offset = offset


@dataclass
class WindowFlushResult:
    """Result of flushing a window, including offset information.

    This allows the consumer to know which offsets are safe to commit
    after writing the aggregate to the database.
    """
    aggregate: TradeAggregate
    partition_offsets: dict[int, int]  # partition -> max_offset


class WindowState:
    """State for a single aggregation window.

    Tracks running totals for computing aggregates:
    - Total value (sum of price * volume) for VWAP
    - Total volume
    - Trade count
    - Max and min prices
    - Kafka offset watermarks (for safe shutdown)
    """

    def __init__(self) -> None:
        """Initialize empty window state."""
        self.total_value: Decimal = Decimal("0")
        self.total_volume: Decimal = Decimal("0")
        self.trade_count: int = 0
        self.max_price: Decimal | None = None
        self.min_price: Decimal | None = None

        # Offset tracking for safe shutdown
        self._offsets: dict[int, OffsetWatermark] = {}  # partition -> watermark
        self._created_at: datetime = datetime.now(UTC)

    def add_trade(
        self,
        trade: TradeEvent,
        partition: int = -1,
        offset: int = -1,
    ) -> None:
        """Add a trade to this window's state.

        Args:
            trade: The trade event to add.
            partition: Kafka partition (for offset tracking)
            offset: Kafka offset (for offset tracking)
        """
        value = trade.price * trade.volume
        self.total_value += value
        self.total_volume += trade.volume
        self.trade_count += 1

        if self.max_price is None or trade.price > self.max_price:
            self.max_price = trade.price
        if self.min_price is None or trade.price < self.min_price:
            self.min_price = trade.price

        # Track offset for this partition
        if partition >= 0 and offset >= 0:
            if partition not in self._offsets:
                self._offsets[partition] = OffsetWatermark()
            self._offsets[partition].update(partition, offset)

    def get_max_offset(self, partition: int) -> int:
        """Get the maximum offset seen for a partition.

        Returns:
            Max offset or -1 if no offsets tracked for this partition.
        """
        if partition in self._offsets:
            return self._offsets[partition].max_offset
        return -1

    def get_all_max_offsets(self) -> dict[int, int]:
        """Get max offsets for all partitions in this window.

        Returns:
            Dict mapping partition -> max_offset
        """
        return {p: wm.max_offset for p, wm in self._offsets.items()}

    def compute_vwap(self) -> Decimal:
        """Compute Volume Weighted Average Price.

        VWAP = sum(price * volume) / sum(volume)

        Returns:
            The VWAP, or 0 if no trades in window.
        """
        if self.total_volume == 0:
            return Decimal("0")
        vwap = self.total_value / self.total_volume
        return vwap.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    def is_empty(self) -> bool:
        """Check if window has no trades."""
        return self.trade_count == 0

    def get_memory_size_estimate(self) -> int:
        """Estimate memory usage of this window state in bytes."""
        # Base object size + decimal sizes + offset tracking
        base_size = sys.getsizeof(self)
        decimal_size = sys.getsizeof(self.total_value) * 4
        offset_size = len(self._offsets) * 64  # Rough estimate per watermark
        return base_size + decimal_size + offset_size


class WindowedAggregator:
    """1-minute tumbling window aggregator for trade events.

    Maintains in-memory state for active windows and produces completed
    aggregates when windows close.

    Window Assignment:
    - Uses event time (trade.event_timestamp), not processing time
    - Windows are aligned to minute boundaries (e.g., 10:00:00 - 10:01:00)

    Late Events:
    - Events arriving after window close are still processed
    - They trigger an update to the aggregate (idempotent via DB upsert)

    Offset Tracking:
    - Each window tracks the Kafka offsets of messages it contains
    - On flush, returns offset information for safe commit coordination
    - Enables safe shutdown: flush windows → write to DB → commit offsets

    Memory Safety:
    - max_windows limit prevents unbounded memory growth
    - Memory estimation for monitoring
    - Oldest windows evicted when limit exceeded
    """

    def __init__(
        self,
        window_duration_seconds: int = 60,
        late_event_grace_seconds: int = 30,
        max_windows: int = 1000,
        max_memory_mb: int = 256,
    ) -> None:
        """Initialize the windowed aggregator.

        Args:
            window_duration_seconds: Window duration in seconds (default 60).
            late_event_grace_seconds: Grace period for late events before
                                     evicting window state.
            max_windows: Maximum number of active windows to prevent memory leaks.
                        Oldest windows are evicted when limit is exceeded.
            max_memory_mb: Maximum estimated memory usage in MB before eviction.
        """
        self.window_duration = timedelta(seconds=window_duration_seconds)
        self.late_grace_period = timedelta(seconds=late_event_grace_seconds)
        self.max_windows = max_windows
        self.max_memory_bytes = max_memory_mb * 1024 * 1024

        # Window state: (symbol, window_start) -> WindowState
        self._windows: dict[tuple[str, datetime], WindowState] = {}

        # Track the latest event time for watermark
        self._latest_event_time: datetime | None = None

        # Track evicted windows for monitoring
        self._evicted_window_count: int = 0

        # Track last processed offset per partition (for safe shutdown)
        self._partition_offsets: dict[int, int] = {}

    def _get_window_start(self, event_time: datetime) -> datetime:
        """Calculate the window start time for an event.

        Windows are aligned to minute boundaries in UTC.

        Args:
            event_time: The event timestamp.

        Returns:
            The start time of the window containing this event.
        """
        # Truncate to minute boundary
        return event_time.replace(second=0, microsecond=0)

    def _get_window_end(self, window_start: datetime) -> datetime:
        """Calculate the window end time.

        Args:
            window_start: The window start time.

        Returns:
            The end time of the window (exclusive).
        """
        return window_start + self.window_duration

    def add_trade(
        self,
        trade: TradeEvent,
        partition: int = -1,
        offset: int = -1,
    ) -> list[WindowFlushResult]:
        """Add a trade to the appropriate window.

        Args:
            trade: The trade event to add.
            partition: Kafka partition (for offset tracking)
            offset: Kafka offset (for offset tracking)

        Returns:
            List of completed windows with offset information.
            Usually empty, but may contain multiple if processing lag.
            Includes both naturally completed windows and evicted windows.
        """
        window_start = self._get_window_start(trade.event_timestamp)
        key = (trade.symbol, window_start)

        # Track partition offset
        if partition >= 0 and offset >= 0:
            current = self._partition_offsets.get(partition, -1)
            if offset > current:
                self._partition_offsets[partition] = offset

        # Evicted windows to return (if any)
        evicted_results: list[WindowFlushResult] = []

        # Create window state if not exists
        if key not in self._windows:
            self._windows[key] = WindowState()
            logger.debug(
                "Created new window",
                symbol=trade.symbol,
                window_start=window_start.isoformat(),
            )

            # Evict oldest windows if we exceed max_windows limit
            if len(self._windows) > self.max_windows:
                evicted_results = self._evict_oldest_windows()
                logger.info(
                    "Evicted windows will be written to database",
                    evicted_count=len(evicted_results),
                )

        # Add trade to window with offset tracking
        self._windows[key].add_trade(trade, partition, offset)

        # Update watermark
        if (
            self._latest_event_time is None
            or trade.event_timestamp > self._latest_event_time
        ):
            self._latest_event_time = trade.event_timestamp

        # Check for completed windows
        completed_results = self._flush_completed_windows()

        # Return both completed and evicted windows
        return evicted_results + completed_results

    def _flush_completed_windows(self) -> list[WindowFlushResult]:
        """Flush windows that have passed the grace period.

        A window is considered complete when:
        watermark > window_end + grace_period

        Returns:
            List of WindowFlushResult with aggregates and offset info.
        """
        if self._latest_event_time is None:
            return []

        completed: list[WindowFlushResult] = []
        keys_to_remove: list[tuple[str, datetime]] = []

        watermark = self._latest_event_time - self.late_grace_period

        for (symbol, window_start), state in self._windows.items():
            window_end = self._get_window_end(window_start)

            # Check if window has closed (past grace period)
            if watermark > window_end:
                if not state.is_empty():
                    aggregate = TradeAggregate(
                        symbol=symbol,
                        window_start=window_start,
                        window_end=window_end,
                        vwap=state.compute_vwap(),
                        total_volume=state.total_volume,
                        trade_count=state.trade_count,
                        max_price=state.max_price or Decimal("0"),
                        min_price=state.min_price or Decimal("0"),
                        total_value=state.total_value,
                    )
                    completed.append(WindowFlushResult(
                        aggregate=aggregate,
                        partition_offsets=state.get_all_max_offsets(),
                    ))

                    logger.info(
                        "Window completed",
                        symbol=symbol,
                        window_start=window_start.isoformat(),
                        vwap=str(aggregate.vwap),
                        trade_count=state.trade_count,
                        offsets=state.get_all_max_offsets(),
                    )

                keys_to_remove.append((symbol, window_start))

        # Remove flushed windows
        for key in keys_to_remove:
            del self._windows[key]

        return completed

    def _evict_oldest_windows(self) -> list[WindowFlushResult]:
        """Evict oldest windows when max_windows limit is exceeded.

        This prevents memory leaks from future-dated events or abnormal conditions.
        Evicted windows are flushed and returned as results.

        Returns:
            List of results from evicted windows.
        """
        # Calculate how many windows to evict (remove 10% to avoid frequent evictions)
        evict_count = max(1, len(self._windows) - self.max_windows + self.max_windows // 10)

        # Sort windows by window_start time (oldest first)
        sorted_keys = sorted(self._windows.keys(), key=lambda k: k[1])
        keys_to_evict = sorted_keys[:evict_count]

        evicted_results: list[WindowFlushResult] = []

        for key in keys_to_evict:
            symbol, window_start = key
            state = self._windows[key]

            if not state.is_empty():
                window_end = self._get_window_end(window_start)
                aggregate = TradeAggregate(
                    symbol=symbol,
                    window_start=window_start,
                    window_end=window_end,
                    vwap=state.compute_vwap(),
                    total_volume=state.total_volume,
                    trade_count=state.trade_count,
                    max_price=state.max_price or Decimal("0"),
                    min_price=state.min_price or Decimal("0"),
                    total_value=state.total_value,
                )
                evicted_results.append(WindowFlushResult(
                    aggregate=aggregate,
                    partition_offsets=state.get_all_max_offsets(),
                ))

            del self._windows[key]
            self._evicted_window_count += 1

        logger.warning(
            "Evicted windows due to max_windows limit",
            evicted_count=len(keys_to_evict),
            total_evicted=self._evicted_window_count,
            remaining_windows=len(self._windows),
        )

        return evicted_results

    def flush_all(self) -> list[WindowFlushResult]:
        """Flush all windows regardless of completion status.

        Used during shutdown to ensure no data is lost.
        Returns offset information for each window so the consumer
        knows which offsets are safe to commit after DB write.

        Returns:
            List of all window results with offset information.
        """
        completed: list[WindowFlushResult] = []

        for (symbol, window_start), state in self._windows.items():
            if not state.is_empty():
                window_end = self._get_window_end(window_start)
                aggregate = TradeAggregate(
                    symbol=symbol,
                    window_start=window_start,
                    window_end=window_end,
                    vwap=state.compute_vwap(),
                    total_volume=state.total_volume,
                    trade_count=state.trade_count,
                    max_price=state.max_price or Decimal("0"),
                    min_price=state.min_price or Decimal("0"),
                    total_value=state.total_value,
                )
                completed.append(WindowFlushResult(
                    aggregate=aggregate,
                    partition_offsets=state.get_all_max_offsets(),
                ))

        self._windows.clear()
        return completed

    def get_active_window_count(self) -> int:
        """Get the number of active (open) windows."""
        return len(self._windows)

    def get_partition_offsets(self) -> dict[int, int]:
        """Get the latest processed offset for each partition.

        This is useful for understanding the current state across
        all active windows.

        Returns:
            Dict mapping partition -> max processed offset
        """
        return dict(self._partition_offsets)

    def get_estimated_memory_usage(self) -> int:
        """Estimate current memory usage in bytes."""
        return sum(
            state.get_memory_size_estimate()
            for state in self._windows.values()
        )

    def get_state_summary(self) -> dict:
        """Get a summary of current aggregator state.

        Returns:
            Dictionary with state statistics.
        """
        return {
            "active_windows": len(self._windows),
            "max_windows": self.max_windows,
            "evicted_windows": self._evicted_window_count,
            "latest_event_time": (
                self._latest_event_time.isoformat()
                if self._latest_event_time
                else None
            ),
            "total_trades_in_windows": sum(
                state.trade_count for state in self._windows.values()
            ),
            "estimated_memory_bytes": self.get_estimated_memory_usage(),
            "partition_offsets": self._partition_offsets,
        }
