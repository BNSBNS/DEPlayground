"""Iron condor vol-selling strategy.

Sells iron condors when IV is elevated, targeting ~30-45 DTE,
short strikes at ~0.16 delta (1 SD), 5-wide wings.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.backtest.models import Leg, Position
from src.backtest.strategies.base import BaseStrategy
from src.models.options_pricer import bs_price
from src.models.options_pricer import delta as bs_delta


class VolSellingStrategy(BaseStrategy):
    """Sell iron condors when IV rank is high."""

    def __init__(
        self,
        iv_threshold: float = 0.25,
        target_dte: int = 30,
        wing_width: float = 5.0,
        short_delta: float = 0.16,
        take_profit_pct: float = 0.50,
        stop_loss_pct: float = 2.0,
        min_dte_exit: int = 7,
    ) -> None:
        self.iv_threshold = iv_threshold
        self.target_dte = target_dte
        self.wing_width = wing_width
        self.short_delta = short_delta
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.min_dte_exit = min_dte_exit

    def generate_signals(
        self,
        current_date: date,
        spot: float,
        iv: float,
        _features: dict | None = None,
    ) -> list[Position]:
        if iv < self.iv_threshold:
            return []

        T = self.target_dte / 252
        r = 0.05

        # Find short strikes near target delta
        put_short = self._find_strike(spot, T, r, iv, "put", self.short_delta)
        call_short = self._find_strike(spot, T, r, iv, "call", self.short_delta)

        put_long = put_short - self.wing_width
        call_long = call_short + self.wing_width

        # Price the legs
        legs = [
            Leg(
                strike=put_long,
                option_type="put",
                side="buy",
                entry_price=bs_price(spot, put_long, T, r, iv, "put"),
                entry_iv=iv,
            ),
            Leg(
                strike=put_short,
                option_type="put",
                side="sell",
                entry_price=bs_price(spot, put_short, T, r, iv, "put"),
                entry_iv=iv,
            ),
            Leg(
                strike=call_short,
                option_type="call",
                side="sell",
                entry_price=bs_price(spot, call_short, T, r, iv, "call"),
                entry_iv=iv,
            ),
            Leg(
                strike=call_long,
                option_type="call",
                side="buy",
                entry_price=bs_price(spot, call_long, T, r, iv, "call"),
                entry_iv=iv,
            ),
        ]

        credit = sum(leg.sign * leg.entry_price for leg in legs)

        expiration = current_date + timedelta(days=self.target_dte)
        return [
            Position(
                ticker="",  # filled by engine
                strategy="iron_condor",
                entry_date=current_date,
                expiration=expiration,
                legs=legs,
                entry_credit=-credit,  # credit is positive when selling
            )
        ]

    def should_exit(
        self,
        position: Position,
        current_date: date,
        _spot: float,
        _iv: float,
    ) -> str | None:
        dte = position.days_to_expiry(current_date)

        # DTE exit
        if dte <= self.min_dte_exit:
            return "dte_exit"

        # Take profit: unrealized P&L >= X% of credit
        if position.entry_credit > 0:
            pnl_pct = position.unrealized_pnl / (position.entry_credit * 100)
            if pnl_pct >= self.take_profit_pct:
                return "take_profit"
            if pnl_pct <= -self.stop_loss_pct:
                return "stop_loss"

        return None

    def _find_strike(
        self, spot: float, T: float, r: float, iv: float, opt_type: str, target_delta: float
    ) -> float:
        """Find strike nearest to target delta (rounded to nearest 5)."""
        best_strike = spot
        best_diff = float("inf")

        # Search ±30% around spot in $5 increments
        low = round(spot * 0.7 / 5) * 5
        high = round(spot * 1.3 / 5) * 5

        for strike in range(int(low), int(high) + 1, 5):
            d = abs(bs_delta(spot, float(strike), T, r, iv, opt_type))
            diff = abs(d - target_delta)
            if diff < best_diff:
                best_diff = diff
                best_strike = float(strike)

        return best_strike
