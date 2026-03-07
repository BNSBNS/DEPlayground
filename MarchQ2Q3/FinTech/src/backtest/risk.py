"""Risk management for the backtest engine.

Enforces: max open positions, per-trade max loss, portfolio delta limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backtest.models import Portfolio, Position


@dataclass
class RiskLimits:
    """Risk parameters for the backtest."""

    max_positions: int = 10
    max_loss_pct: float = 0.02  # 2% max loss per trade (of NAV)
    max_delta_pct: float = 0.05  # ±5% net dollar delta / NAV
    slippage_per_leg: float = 0.05  # bid-ask cost per option leg
    commission_per_contract: float = 0.65


class RiskManager:
    """Enforces risk limits on the portfolio."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def can_open_new(self, portfolio: Portfolio) -> bool:
        """Check if we can open a new position."""
        return not len(portfolio.open_positions) >= self.limits.max_positions

    def approve(self, position: Position, portfolio: Portfolio) -> bool:
        """Check if a specific position passes risk checks."""
        if not self.can_open_new(portfolio):
            return False

        # Max loss check: theoretical max loss <= max_loss_pct * equity
        max_loss = self._theoretical_max_loss(position)
        if max_loss > self.limits.max_loss_pct * portfolio.equity:
            return False

        # Delta check after adding position
        projected_delta = portfolio.net_dollar_delta
        return not abs(projected_delta) > self.limits.max_delta_pct

    def transaction_cost(self, position: Position) -> float:
        """Calculate total transaction costs for a position."""
        n_legs = len(position.legs)
        total_contracts = sum(leg.quantity for leg in position.legs)
        slippage = n_legs * self.limits.slippage_per_leg * 100  # per 100 shares
        commission = total_contracts * self.limits.commission_per_contract
        return slippage + commission

    def _theoretical_max_loss(self, position: Position) -> float:
        """Compute theoretical max loss (wing width - credit for spreads)."""
        strikes = sorted(leg.strike for leg in position.legs)
        if len(strikes) >= 2:
            wing_width = strikes[-1] - strikes[0]
            return (wing_width - position.entry_credit) * 100
        return position.entry_credit * 100
