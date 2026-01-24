"""Trade event generator with realistic patterns.

This module generates synthetic energy trade events that simulate real market behavior,
including normal trading periods and burst patterns during market volatility.
"""

import random
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterator, TypedDict
from uuid import uuid4

from src.common.models import TradeEvent, TradeSide


class SymbolConfig(TypedDict):
    """Configuration for a trading symbol."""

    base_price: Decimal
    volatility: float


# Energy trading symbols with realistic base prices
SYMBOLS: dict[str, SymbolConfig] = {
    "POWER_DE": {"base_price": Decimal("85.50"), "volatility": 0.02},  # German power
    "POWER_FR": {"base_price": Decimal("82.30"), "volatility": 0.025},  # French power
    "POWER_NL": {"base_price": Decimal("88.20"), "volatility": 0.022},  # Dutch power
    "GAS_NL": {"base_price": Decimal("42.75"), "volatility": 0.03},  # TTF gas
    "GAS_UK": {"base_price": Decimal("45.20"), "volatility": 0.035},  # UK NBP gas
    "BRENT_OIL": {"base_price": Decimal("78.50"), "volatility": 0.015},  # Brent crude
    "CARBON_EU": {"base_price": Decimal("65.80"), "volatility": 0.04},  # EU ETS carbon
}

# Trader IDs for simulation
TRADER_IDS = [
    "TRADER_001",
    "TRADER_002",
    "TRADER_003",
    "TRADER_004",
    "TRADER_005",
    "ALGO_BOT_A",
    "ALGO_BOT_B",
    "MARKET_MAKER",
]


class TradeGenerator:
    """Generates realistic energy trade events.

    The generator simulates market behavior with:
    - Multiple energy commodities with different volatility profiles
    - Random walk price movements around base prices
    - Volume distributions that reflect typical trading patterns
    - Burst patterns to simulate market volatility events
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        seed: int | None = None,
    ) -> None:
        """Initialize the trade generator.

        Args:
            symbols: List of symbols to generate trades for.
                    If None, uses all available symbols.
            seed: Random seed for reproducibility. If None, uses system entropy.
        """
        self.symbols = symbols or list(SYMBOLS.keys())
        self.rng = random.Random(seed)

        # Track current prices for random walk simulation
        self._current_prices: dict[str, Decimal] = {
            symbol: SYMBOLS[symbol]["base_price"]
            for symbol in self.symbols
        }

    def _generate_price(self, symbol: str) -> Decimal:
        """Generate a realistic price using random walk.

        Prices follow a random walk with drift, bounded by +/- 20% of base price.
        """
        config = SYMBOLS[symbol]
        base_price = config["base_price"]
        volatility = config["volatility"]

        current = self._current_prices[symbol]

        # Random walk with mean reversion
        change_pct = self.rng.gauss(0, volatility)
        mean_reversion = float((base_price - current) / base_price) * 0.1

        new_price = current * Decimal(str(1 + change_pct + mean_reversion))

        # Bound prices to +/- 20% of base
        min_price = base_price * Decimal("0.8")
        max_price = base_price * Decimal("1.2")
        new_price = max(min_price, min(max_price, new_price))

        # Round to 2 decimal places (typical for energy markets)
        new_price = new_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self._current_prices[symbol] = new_price
        return new_price

    def _generate_volume(self, is_burst: bool = False) -> Decimal:
        """Generate a realistic trade volume.

        Volume follows a log-normal distribution to simulate the heavy-tailed
        nature of trading volumes (many small trades, few large ones).
        """
        # Base volume in MW for power or appropriate unit
        if is_burst:
            # During bursts, volumes are typically higher
            base = self.rng.lognormvariate(3.5, 1.2)  # Higher mean
        else:
            base = self.rng.lognormvariate(2.5, 1.0)

        # Round to 2 decimal places
        volume = Decimal(str(round(base, 2)))

        # Minimum volume of 0.1
        return max(Decimal("0.1"), volume)

    def generate_trade(self, *, is_burst: bool = False) -> TradeEvent:
        """Generate a single trade event.

        Args:
            is_burst: If True, generates higher volume trades typical of
                     volatile market conditions.

        Returns:
            A TradeEvent with realistic values.
        """
        symbol = self.rng.choice(self.symbols)
        price = self._generate_price(symbol)
        volume = self._generate_volume(is_burst=is_burst)
        side = self.rng.choice([TradeSide.BUY, TradeSide.SELL])
        trader_id = self.rng.choice(TRADER_IDS)

        return TradeEvent(
            trade_id=uuid4(),
            symbol=symbol,
            price=price,
            volume=volume,
            side=side,
            trader_id=trader_id,
            event_timestamp=datetime.now(UTC),
        )

    def generate_trades(
        self,
        count: int,
        *,
        is_burst: bool = False,
    ) -> Iterator[TradeEvent]:
        """Generate multiple trade events.

        Args:
            count: Number of trades to generate.
            is_burst: If True, generates burst-mode trades.

        Yields:
            TradeEvent instances.
        """
        for _ in range(count):
            yield self.generate_trade(is_burst=is_burst)

    def reset_prices(self) -> None:
        """Reset all prices to their base values."""
        self._current_prices = {
            symbol: SYMBOLS[symbol]["base_price"]
            for symbol in self.symbols
        }
