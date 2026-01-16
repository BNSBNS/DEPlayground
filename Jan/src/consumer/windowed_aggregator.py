"""Windowed aggregation for trade events.

This module implements 1-minute tumbling window aggregation for trade events,
computing VWAP, total volume, trade count, and price extremes per symbol.
"""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterator

from src.common.logging_config import get_logger
from src.common.models import TradeAggregate, TradeEvent

logger = get_logger(__name__)


class WindowState:
    """State for a single aggregation window.

    Tracks running totals for computing aggregates:
    - Total value (sum of price * volume) for VWAP
    - Total volume
    - Trade count
    - Max and min prices
    """

    def __init__(self) -> None:
        """Initialize empty window state."""
        self.total_value: Decimal = Decimal("0")
        self.total_volume: Decimal = Decimal("0")
        self.trade_count: int = 0
        self.max_price: Decimal | None = None
        self.min_price: Decimal | None = None

    def add_trade(self, trade: TradeEvent) -> None:
        """Add a trade to this window's state.

        Args:
            trade: The trade event to add.
        """
        value = trade.price * trade.volume
        self.total_value += value
        self.total_volume += trade.volume
        self.trade_count += 1

        if self.max_price is None or trade.price > self.max_price:
            self.max_price = trade.price
        if self.min_price is None or trade.price < self.min_price:
            self.min_price = trade.price

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

    State Management:
    - In-memory state, no external state store required
    - State is lost on restart, but at-least-once + idempotent writes
      ensures correctness after replay from last committed offset
    """

    def __init__(
        self,
        window_duration_seconds: int = 60,
        late_event_grace_seconds: int = 30,
    ) -> None:
        """Initialize the windowed aggregator.

        Args:
            window_duration_seconds: Window duration in seconds (default 60).
            late_event_grace_seconds: Grace period for late events before
                                     evicting window state.
        """
        self.window_duration = timedelta(seconds=window_duration_seconds)
        self.late_grace_period = timedelta(seconds=late_event_grace_seconds)

        # Window state: (symbol, window_start) -> WindowState
        self._windows: dict[tuple[str, datetime], WindowState] = {}

        # Track the latest event time for watermark
        self._latest_event_time: datetime | None = None

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

    def add_trade(self, trade: TradeEvent) -> list[TradeAggregate]:
        """Add a trade to the appropriate window.

        Args:
            trade: The trade event to add.

        Returns:
            List of completed aggregates (windows that have closed).
            Usually empty, but may contain multiple if processing lag.
        """
        window_start = self._get_window_start(trade.event_timestamp)
        key = (trade.symbol, window_start)

        # Create window state if not exists
        if key not in self._windows:
            self._windows[key] = WindowState()
            logger.debug(
                "Created new window",
                symbol=trade.symbol,
                window_start=window_start.isoformat(),
            )

        # Add trade to window
        self._windows[key].add_trade(trade)

        # Update watermark
        if (
            self._latest_event_time is None
            or trade.event_timestamp > self._latest_event_time
        ):
            self._latest_event_time = trade.event_timestamp

        # Check for completed windows
        return self._flush_completed_windows()

    def _flush_completed_windows(self) -> list[TradeAggregate]:
        """Flush windows that have passed the grace period.

        A window is considered complete when:
        watermark > window_end + grace_period

        Returns:
            List of completed TradeAggregate objects.
        """
        if self._latest_event_time is None:
            return []

        completed: list[TradeAggregate] = []
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
                    completed.append(aggregate)

                    logger.info(
                        "Window completed",
                        symbol=symbol,
                        window_start=window_start.isoformat(),
                        vwap=str(aggregate.vwap),
                        trade_count=state.trade_count,
                    )

                keys_to_remove.append((symbol, window_start))

        # Remove flushed windows
        for key in keys_to_remove:
            del self._windows[key]

        return completed

    def flush_all(self) -> list[TradeAggregate]:
        """Flush all windows regardless of completion status.

        Used during shutdown to ensure no data is lost.

        Returns:
            List of all window aggregates.
        """
        completed: list[TradeAggregate] = []

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
                completed.append(aggregate)

        self._windows.clear()
        return completed

    def get_active_window_count(self) -> int:
        """Get the number of active (open) windows."""
        return len(self._windows)

    def get_state_summary(self) -> dict[str, int | str | None]:
        """Get a summary of current aggregator state.

        Returns:
            Dictionary with state statistics.
        """
        return {
            "active_windows": len(self._windows),
            "latest_event_time": (
                self._latest_event_time.isoformat()
                if self._latest_event_time
                else None
            ),
            "total_trades_in_windows": sum(
                state.trade_count for state in self._windows.values()
            ),
        }
