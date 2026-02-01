"""CQRS Read Models - Optimized for queries.

Read models are denormalized views of data optimized for specific query patterns.
Unlike the normalized write model (trade_aggregates), read models:
- Are denormalized for fast reads
- May contain computed/derived fields
- Are updated asynchronously via projections
- Can be rebuilt from events if needed

These models correspond to the SQL tables in 004_cqrs_read_models.sql
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VWAPSummaryReadModel(BaseModel):
    """Read model for VWAP summary per symbol.

    Optimized for queries like:
    - "What's the current VWAP for POWER_DE?"
    - "Show me all symbols with their VWAP trends"
    - "Which symbols have high volume?"

    This model is denormalized with pre-computed rolling averages,
    avoiding expensive aggregate queries at read time.
    """

    model_config = ConfigDict(validate_assignment=True)

    symbol: str = Field(description="Trading symbol")

    # Current values
    current_vwap: Decimal | None = Field(
        default=None,
        description="VWAP from the latest completed window",
    )
    current_lmp: Decimal | None = Field(
        default=None,
        description="LMP from the latest completed window",
    )

    # Rolling averages (pre-computed by projection)
    vwap_1h: Decimal | None = Field(
        default=None,
        description="1-hour rolling VWAP",
    )
    vwap_24h: Decimal | None = Field(
        default=None,
        description="24-hour rolling VWAP",
    )

    # Volume statistics
    total_volume_24h: Decimal | None = Field(
        default=None,
        description="Total volume in last 24 hours",
    )
    trade_count_24h: int | None = Field(
        default=None,
        description="Number of trades in last 24 hours",
    )

    # Metadata
    last_updated: datetime | None = Field(
        default=None,
        description="When this read model was last updated",
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "symbol": self.symbol,
            "current_vwap": str(self.current_vwap) if self.current_vwap else None,
            "current_lmp": str(self.current_lmp) if self.current_lmp else None,
            "vwap_1h": str(self.vwap_1h) if self.vwap_1h else None,
            "vwap_24h": str(self.vwap_24h) if self.vwap_24h else None,
            "total_volume_24h": str(self.total_volume_24h) if self.total_volume_24h else None,
            "trade_count_24h": self.trade_count_24h,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @property
    def vwap_change_1h_pct(self) -> float | None:
        """Calculate percentage change from 1h VWAP to current."""
        if self.current_vwap and self.vwap_1h and self.vwap_1h != 0:
            return float((self.current_vwap - self.vwap_1h) / self.vwap_1h * 100)
        return None


class SymbolActivityReadModel(BaseModel):
    """Read model for symbol trading activity.

    Optimized for queries like:
    - "Which symbols are currently active?"
    - "What's the trading frequency for POWER_DE?"
    - "Show inactive symbols"

    This model provides real-time activity metrics without
    needing to scan trade history.
    """

    model_config = ConfigDict(validate_assignment=True)

    symbol: str = Field(description="Trading symbol")

    # Activity metrics
    last_trade_time: datetime | None = Field(
        default=None,
        description="Timestamp of most recent trade",
    )
    trades_last_minute: int = Field(
        default=0,
        description="Number of trades in the last minute",
    )
    avg_trade_size: Decimal | None = Field(
        default=None,
        description="Average trade volume",
    )

    # Status
    is_active: bool = Field(
        default=False,
        description="True if traded within last 5 minutes",
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "symbol": self.symbol,
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
            "trades_last_minute": self.trades_last_minute,
            "avg_trade_size": str(self.avg_trade_size) if self.avg_trade_size else None,
            "is_active": self.is_active,
        }


class LMPBreakdownReadModel(BaseModel):
    """Read model for LMP breakdown by symbol.

    Optimized for energy market analysis queries:
    - "What's driving the LMP in Germany?"
    - "Show congestion trends across zones"
    - "Compare energy vs loss components"
    """

    model_config = ConfigDict(validate_assignment=True)

    symbol: str = Field(description="Trading symbol")
    zone: str = Field(default="", description="Pricing zone")

    # Current LMP breakdown
    lmp_total: Decimal | None = Field(default=None)
    lmp_energy: Decimal | None = Field(default=None)
    lmp_congestion: Decimal | None = Field(default=None)
    lmp_loss: Decimal | None = Field(default=None)

    # Historical comparison
    lmp_1h_ago: Decimal | None = Field(default=None)
    lmp_24h_ago: Decimal | None = Field(default=None)

    # Statistics
    avg_congestion_24h: Decimal | None = Field(default=None)
    max_congestion_24h: Decimal | None = Field(default=None)

    last_updated: datetime | None = Field(default=None)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "symbol": self.symbol,
            "zone": self.zone,
            "lmp_total": str(self.lmp_total) if self.lmp_total else None,
            "lmp_energy": str(self.lmp_energy) if self.lmp_energy else None,
            "lmp_congestion": str(self.lmp_congestion) if self.lmp_congestion else None,
            "lmp_loss": str(self.lmp_loss) if self.lmp_loss else None,
            "lmp_1h_ago": str(self.lmp_1h_ago) if self.lmp_1h_ago else None,
            "lmp_24h_ago": str(self.lmp_24h_ago) if self.lmp_24h_ago else None,
            "avg_congestion_24h": str(self.avg_congestion_24h) if self.avg_congestion_24h else None,
            "max_congestion_24h": str(self.max_congestion_24h) if self.max_congestion_24h else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @property
    def congestion_ratio(self) -> float | None:
        """Calculate congestion as percentage of total LMP."""
        if self.lmp_total and self.lmp_congestion and self.lmp_total != 0:
            return float(self.lmp_congestion / self.lmp_total * 100)
        return None
