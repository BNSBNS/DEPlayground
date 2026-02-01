"""Gold Layer - Aggregated business-level data.

The Gold layer contains:
- Pre-computed aggregations (VWAP, LMP)
- Business-ready metrics
- Dimensional data for BI tools

Aggregations from Silver:
1. Time-windowed VWAP (1-min, 15-min, hourly)
2. LMP calculations with components
3. Volume statistics
4. Price volatility metrics

This layer is optimized for:
- Dashboard queries (Grafana, Superset, PowerBI)
- Real-time analytics
- Regulatory reporting

The Gold layer can be updated by:
- Streaming: Real-time from Kafka consumer
- Batch: Periodic recomputation from Silver
- Hybrid: Both (Lakehouse advantage)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Iterator

import structlog

from src.pricing.lmp import compute_lmp
from src.pricing.models import LMPComponents

logger = structlog.get_logger(__name__)


@dataclass
class GoldAggregate:
    """Aggregated record in the Gold layer.

    This is the final, business-ready format for analytics.
    """

    # Dimensions
    symbol: str
    window_start: datetime
    window_end: datetime

    # VWAP metrics
    vwap: Decimal
    total_volume: Decimal
    trade_count: int
    max_price: Decimal
    min_price: Decimal

    # LMP components
    lmp: Decimal | None = None
    lmp_energy: Decimal | None = None
    lmp_congestion: Decimal | None = None
    lmp_loss: Decimal | None = None

    # Derived metrics
    price_volatility: Decimal | None = None
    avg_trade_size: Decimal | None = None

    # Metadata
    computed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage/API."""
        return {
            "symbol": self.symbol,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "vwap": str(self.vwap),
            "total_volume": str(self.total_volume),
            "trade_count": self.trade_count,
            "max_price": str(self.max_price),
            "min_price": str(self.min_price),
            "lmp": str(self.lmp) if self.lmp else None,
            "lmp_energy": str(self.lmp_energy) if self.lmp_energy else None,
            "lmp_congestion": str(self.lmp_congestion) if self.lmp_congestion else None,
            "lmp_loss": str(self.lmp_loss) if self.lmp_loss else None,
            "price_volatility": str(self.price_volatility) if self.price_volatility else None,
            "avg_trade_size": str(self.avg_trade_size) if self.avg_trade_size else None,
            "_computed_at": self.computed_at.isoformat(),
        }

    def to_db_tuple(self) -> tuple:
        """Convert to tuple for PostgreSQL insertion."""
        return (
            self.symbol,
            self.window_start,
            self.window_end,
            self.vwap,
            self.total_volume,
            self.trade_count,
            self.max_price,
            self.min_price,
            self.lmp,
            self.lmp_energy,
            self.lmp_congestion,
            self.lmp_loss,
        )


@dataclass
class TradeAccumulator:
    """Accumulates trades for a single window."""

    symbol: str
    window_start: datetime
    window_end: datetime
    total_value: Decimal = Decimal("0")
    total_volume: Decimal = Decimal("0")
    trade_count: int = 0
    max_price: Decimal | None = None
    min_price: Decimal | None = None

    def add_trade(self, price: Decimal, volume: Decimal) -> None:
        """Add a trade to the accumulator."""
        self.total_value += price * volume
        self.total_volume += volume
        self.trade_count += 1

        if self.max_price is None or price > self.max_price:
            self.max_price = price
        if self.min_price is None or price < self.min_price:
            self.min_price = price

    def compute_vwap(self) -> Decimal:
        """Compute VWAP from accumulated values."""
        if self.total_volume == 0:
            return Decimal("0")
        return (self.total_value / self.total_volume).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )

    def to_gold_aggregate(self) -> GoldAggregate:
        """Convert to Gold aggregate with all metrics."""
        vwap = self.compute_vwap()

        # Calculate LMP
        lmp_components = compute_lmp(
            symbol=self.symbol,
            vwap=vwap,
            max_price=self.max_price,
            min_price=self.min_price,
        )

        # Calculate derived metrics
        price_volatility = None
        if self.max_price and self.min_price and vwap > 0:
            price_volatility = ((self.max_price - self.min_price) / vwap).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        avg_trade_size = None
        if self.trade_count > 0:
            avg_trade_size = (self.total_volume / self.trade_count).quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            )

        return GoldAggregate(
            symbol=self.symbol,
            window_start=self.window_start,
            window_end=self.window_end,
            vwap=vwap,
            total_volume=self.total_volume,
            trade_count=self.trade_count,
            max_price=self.max_price or Decimal("0"),
            min_price=self.min_price or Decimal("0"),
            lmp=lmp_components.total,
            lmp_energy=lmp_components.energy,
            lmp_congestion=lmp_components.congestion,
            lmp_loss=lmp_components.loss,
            price_volatility=price_volatility,
            avg_trade_size=avg_trade_size,
        )


class GoldLayer:
    """Gold layer for aggregated business data.

    Provides both batch and streaming aggregation:
    - Batch: Recompute from Silver records
    - Streaming: Update from real-time events

    Example usage:
        >>> gold = GoldLayer(storage_path="s3://bucket/gold/aggregates")
        >>>
        >>> # Batch processing
        >>> gold.process_silver_records(silver.read_records())
        >>>
        >>> # Streaming (from Kafka consumer)
        >>> gold.add_trade(symbol, price, volume, timestamp)
        >>> aggregates = gold.flush_completed_windows()
    """

    def __init__(
        self,
        storage_path: str | Path,
        window_duration_seconds: int = 60,
        late_grace_seconds: int = 30,
    ):
        """Initialize the Gold layer.

        Args:
            storage_path: Path to store Gold data
            window_duration_seconds: Window duration for aggregation
            late_grace_seconds: Grace period for late events
        """
        self.storage_path = Path(storage_path)
        self.window_duration = timedelta(seconds=window_duration_seconds)
        self.late_grace = timedelta(seconds=late_grace_seconds)

        # Active windows: (symbol, window_start) -> TradeAccumulator
        self._windows: dict[tuple[str, datetime], TradeAccumulator] = {}
        self._completed: list[GoldAggregate] = []
        self._watermark: datetime | None = None

        logger.info(
            "Gold layer initialized",
            storage_path=str(self.storage_path),
            window_duration=window_duration_seconds,
        )

    def _get_window_start(self, event_time: datetime) -> datetime:
        """Calculate window start for an event."""
        return event_time.replace(second=0, microsecond=0)

    def add_trade(
        self,
        symbol: str,
        price: Decimal,
        volume: Decimal,
        event_timestamp: datetime,
    ) -> list[GoldAggregate]:
        """Add a trade and return any completed aggregates.

        This is the streaming interface, called for each trade event.

        Args:
            symbol: Trading symbol
            price: Trade price
            volume: Trade volume
            event_timestamp: Event timestamp

        Returns:
            List of completed aggregates (if any windows closed)
        """
        window_start = self._get_window_start(event_timestamp)
        window_end = window_start + self.window_duration
        key = (symbol, window_start)

        # Get or create accumulator
        if key not in self._windows:
            self._windows[key] = TradeAccumulator(
                symbol=symbol,
                window_start=window_start,
                window_end=window_end,
            )

        self._windows[key].add_trade(price, volume)

        # Update watermark
        if self._watermark is None or event_timestamp > self._watermark:
            self._watermark = event_timestamp

        # Flush completed windows
        return self._flush_completed()

    def _flush_completed(self) -> list[GoldAggregate]:
        """Flush windows that have passed the grace period."""
        if self._watermark is None:
            return []

        completed = []
        keys_to_remove = []
        cutoff = self._watermark - self.late_grace

        for key, accumulator in self._windows.items():
            if accumulator.window_end < cutoff:
                if accumulator.trade_count > 0:
                    gold = accumulator.to_gold_aggregate()
                    completed.append(gold)
                    self._completed.append(gold)
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._windows[key]

        return completed

    def flush_all(self) -> list[GoldAggregate]:
        """Flush all windows regardless of completion.

        Use during shutdown to ensure no data is lost.
        """
        completed = []
        for accumulator in self._windows.values():
            if accumulator.trade_count > 0:
                gold = accumulator.to_gold_aggregate()
                completed.append(gold)
                self._completed.append(gold)

        self._windows.clear()
        return completed

    def process_silver_batch(
        self,
        silver_records: Iterator[Any],
    ) -> dict[str, int]:
        """Process Silver records in batch mode.

        This recomputes aggregates from historical data.

        Args:
            silver_records: Iterator of Silver records

        Returns:
            Statistics: windows_created, records_processed
        """
        stats = {"records_processed": 0, "windows_completed": 0}

        for record in silver_records:
            # Add trade (handles window management)
            completed = self.add_trade(
                symbol=record.symbol,
                price=record.price,
                volume=record.volume,
                event_timestamp=record.event_timestamp,
            )
            stats["records_processed"] += 1
            stats["windows_completed"] += len(completed)

        # Flush remaining windows
        final = self.flush_all()
        stats["windows_completed"] += len(final)

        # Persist to storage
        self._persist_completed()

        return stats

    def _persist_completed(self) -> None:
        """Persist completed aggregates to storage."""
        if not self._completed:
            return

        self.storage_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        file_path = self.storage_path / f"aggregates_{timestamp}.parquet"

        try:
            import pandas as pd

            df = pd.DataFrame([a.to_dict() for a in self._completed])
            df.to_parquet(file_path, index=False)
            logger.info(
                "Gold aggregates persisted",
                count=len(self._completed),
                file=str(file_path),
            )
        except ImportError:
            import json

            json_path = file_path.with_suffix(".json")
            with open(json_path, "w") as f:
                json.dump([a.to_dict() for a in self._completed], f)

        self._completed.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get Gold layer statistics."""
        return {
            "storage_path": str(self.storage_path),
            "window_duration_seconds": self.window_duration.total_seconds(),
            "active_windows": len(self._windows),
            "completed_pending": len(self._completed),
            "watermark": self._watermark.isoformat() if self._watermark else None,
        }

    def read_aggregates(
        self,
        symbol: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Iterator[GoldAggregate]:
        """Read Gold aggregates from storage.

        Args:
            symbol: Optional symbol filter
            start_time: Optional start time filter
            end_time: Optional end time filter

        Yields:
            GoldAggregate objects
        """
        try:
            import pandas as pd

            for file_path in self.storage_path.glob("**/*.parquet"):
                df = pd.read_parquet(file_path)

                # Apply filters
                if symbol:
                    df = df[df["symbol"] == symbol]

                for _, row in df.iterrows():
                    window_start = datetime.fromisoformat(row["window_start"])
                    if start_time and window_start < start_time:
                        continue
                    if end_time and window_start >= end_time:
                        continue

                    yield GoldAggregate(
                        symbol=row["symbol"],
                        window_start=window_start,
                        window_end=datetime.fromisoformat(row["window_end"]),
                        vwap=Decimal(str(row["vwap"])),
                        total_volume=Decimal(str(row["total_volume"])),
                        trade_count=int(row["trade_count"]),
                        max_price=Decimal(str(row["max_price"])),
                        min_price=Decimal(str(row["min_price"])),
                        lmp=Decimal(str(row["lmp"])) if row.get("lmp") else None,
                        lmp_energy=Decimal(str(row["lmp_energy"])) if row.get("lmp_energy") else None,
                        lmp_congestion=Decimal(str(row["lmp_congestion"])) if row.get("lmp_congestion") else None,
                        lmp_loss=Decimal(str(row["lmp_loss"])) if row.get("lmp_loss") else None,
                    )
        except ImportError:
            pass  # No pandas
