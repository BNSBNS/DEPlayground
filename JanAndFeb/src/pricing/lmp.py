"""Location Marginal Pricing (LMP) calculation.

LMP represents the incremental cost of serving one more unit of load at a
specific location. It's the standard pricing mechanism in US energy markets
(PJM, NYISO, ISO-NE, ERCOT, CAISO, MISO, SPP).

LMP = Energy Component + Congestion Component + Loss Component

Where:
- Energy Component: System marginal price (cost of the next MW of generation)
- Congestion Component: Shadow price of transmission constraints * shift factor
- Loss Component: Marginal cost of losses at that location

For this learning platform, we use simplified calculations that demonstrate
the concept while maintaining the mathematical structure.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog

from src.pricing.models import LMPComponents, PricingNode, PricingNodeRegistry

logger = structlog.get_logger(__name__)


class LMPCalculator:
    """Calculator for Location Marginal Pricing.

    This calculator provides LMP estimates based on:
    - VWAP (as proxy for system energy price)
    - Node-specific loss factors
    - Configurable congestion estimates

    In production energy markets, LMP is calculated by the ISO/RTO using:
    - Security-constrained economic dispatch (SCED)
    - Real-time power flow analysis
    - Transmission constraint shadow prices

    This simplified implementation is for learning purposes and demonstrates
    the structure of LMP calculations.

    Example:
        >>> calculator = LMPCalculator()
        >>> vwap = Decimal("50.00")  # EUR/MWh
        >>> lmp = calculator.calculate("POWER_DE", vwap)
        >>> print(f"LMP: {lmp.total} (Energy: {lmp.energy}, Congestion: {lmp.congestion}, Loss: {lmp.loss})")
    """

    def __init__(
        self,
        congestion_base: Decimal = Decimal("0"),
        congestion_volatility: Decimal = Decimal("0.10"),
    ):
        """Initialize the LMP calculator.

        Args:
            congestion_base: Base congestion cost (added to all calculations)
            congestion_volatility: How much congestion varies with price volatility
        """
        self.congestion_base = congestion_base
        self.congestion_volatility = congestion_volatility

    def calculate(
        self,
        symbol: str,
        vwap: Decimal,
        price_volatility: Decimal | None = None,
        volume_ratio: Decimal | None = None,
    ) -> LMPComponents:
        """Calculate LMP for a symbol based on VWAP and market conditions.

        The calculation uses:
        1. Energy = VWAP (simplified, assumes VWAP approximates system marginal price)
        2. Congestion = f(node sensitivity, price volatility, base congestion)
        3. Loss = VWAP * loss_factor

        Args:
            symbol: Trading symbol (used to look up node configuration)
            vwap: Volume Weighted Average Price for the window
            price_volatility: Optional price volatility measure (max-min)/avg
            volume_ratio: Optional volume ratio vs average (for congestion)

        Returns:
            LMPComponents with energy, congestion, and loss breakdown
        """
        # Get node configuration
        node = PricingNodeRegistry.get_node(symbol)

        # Handle zero/invalid VWAP
        if vwap <= 0:
            return LMPComponents.zero()

        # 1. Energy Component = VWAP
        # In real markets, this would be the system lambda (marginal cost of generation)
        energy = vwap

        # 2. Loss Component = VWAP * loss_factor
        # Marginal losses increase with load (losses ~ I^2)
        loss = (vwap * node.base_loss_factor).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )

        # 3. Congestion Component
        # Simplified: based on node sensitivity and price volatility
        congestion = self._calculate_congestion(
            node=node,
            vwap=vwap,
            price_volatility=price_volatility,
            volume_ratio=volume_ratio,
        )

        result = LMPComponents(energy=energy, congestion=congestion, loss=loss)

        logger.debug(
            "LMP calculated",
            symbol=symbol,
            zone=node.zone,
            vwap=str(vwap),
            lmp_total=str(result.total),
            energy=str(energy),
            congestion=str(congestion),
            loss=str(loss),
        )

        return result

    def _calculate_congestion(
        self,
        node: PricingNode,
        vwap: Decimal,
        price_volatility: Decimal | None,
        volume_ratio: Decimal | None,
    ) -> Decimal:
        """Calculate congestion component.

        In real markets, congestion = sum(constraint_shadow_price * shift_factor)
        where shift factors represent how much a node contributes to a constraint.

        Our simplified model:
        - Base congestion from historical data
        - Volatility adjustment (high volatility often correlates with congestion)
        - Volume adjustment (high volume can indicate stress)

        Args:
            node: Pricing node configuration
            vwap: Volume weighted average price
            price_volatility: Price volatility measure
            volume_ratio: Volume ratio vs average

        Returns:
            Congestion component value
        """
        # Reference nodes have zero congestion by definition
        if node.is_reference_node:
            return Decimal("0")

        # Start with typical/historical congestion
        congestion = node.typical_congestion_adder + self.congestion_base

        # Adjust for price volatility (proxy for market stress)
        if price_volatility is not None and price_volatility > 0:
            # Higher volatility suggests potential transmission constraints
            volatility_factor = min(price_volatility, Decimal("1.0"))
            congestion += (
                vwap
                * node.congestion_sensitivity
                * volatility_factor
                * self.congestion_volatility
            )

        # Adjust for volume (high volume can indicate congestion)
        if volume_ratio is not None and volume_ratio > Decimal("1.5"):
            # Volume significantly above average
            volume_factor = min(volume_ratio - Decimal("1"), Decimal("1.0"))
            congestion += (
                vwap * node.congestion_sensitivity * volume_factor * Decimal("0.05")
            )

        return congestion.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def compute_lmp(
    symbol: str,
    vwap: Decimal,
    max_price: Decimal | None = None,
    min_price: Decimal | None = None,
    total_volume: Decimal | None = None,
    avg_volume: Decimal | None = None,
) -> LMPComponents:
    """Convenience function to compute LMP with common parameters.

    This is the main entry point for LMP calculation in the aggregation pipeline.

    Args:
        symbol: Trading symbol
        vwap: Volume Weighted Average Price
        max_price: Maximum price in window (for volatility calculation)
        min_price: Minimum price in window (for volatility calculation)
        total_volume: Total volume in window
        avg_volume: Average volume (for volume ratio calculation)

    Returns:
        LMPComponents with full breakdown

    Example:
        >>> lmp = compute_lmp(
        ...     symbol="POWER_DE",
        ...     vwap=Decimal("50.00"),
        ...     max_price=Decimal("55.00"),
        ...     min_price=Decimal("45.00"),
        ... )
        >>> print(f"Total LMP: {lmp.total}")
    """
    # Calculate price volatility if we have range
    price_volatility = None
    if max_price is not None and min_price is not None and vwap > 0:
        price_range = max_price - min_price
        price_volatility = price_range / vwap

    # Calculate volume ratio if we have averages
    volume_ratio = None
    if total_volume is not None and avg_volume is not None and avg_volume > 0:
        volume_ratio = total_volume / avg_volume

    calculator = LMPCalculator()
    return calculator.calculate(
        symbol=symbol,
        vwap=vwap,
        price_volatility=price_volatility,
        volume_ratio=volume_ratio,
    )
