"""Data models for the backtest engine.

Core types: Leg, Trade, Position, Portfolio.

A Position represents one options spread (e.g., iron condor = 4 legs).
A Trade is the record of an opened+closed position with realized P&L.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


@dataclass
class Leg:
    """A single option leg in a multi-leg position."""

    strike: float
    option_type: str  # "call" or "put"
    side: str  # "buy" or "sell"
    quantity: int = 1
    entry_price: float = 0.0
    current_price: float = 0.0
    entry_iv: float = 0.0
    current_iv: float = 0.0
    delta: float = 0.0

    @property
    def sign(self) -> int:
        """+1 for long, -1 for short."""
        return 1 if self.side == "buy" else -1

    @property
    def unrealized_pnl(self) -> float:
        """Per-contract unrealized P&L (x100 multiplier)."""
        return self.sign * (self.current_price - self.entry_price) * self.quantity * 100


@dataclass
class Position:
    """A multi-leg options position (e.g., iron condor, straddle)."""

    ticker: str
    strategy: str
    entry_date: date
    expiration: date
    legs: list[Leg]
    entry_credit: float = 0.0  # net credit received (positive = credit)

    @property
    def is_expired(self) -> bool:
        return False  # set by engine when current_date >= expiration

    @property
    def unrealized_pnl(self) -> float:
        return sum(leg.unrealized_pnl for leg in self.legs)

    @property
    def net_delta(self) -> float:
        return sum(leg.delta * leg.sign * leg.quantity for leg in self.legs)

    def days_to_expiry(self, current_date: date) -> int:
        return max((self.expiration - current_date).days, 0)


@dataclass
class Trade:
    """Completed (closed) position with realized P&L."""

    ticker: str
    strategy: str
    entry_date: date
    exit_date: date
    entry_credit: float
    exit_debit: float
    pnl: float
    legs: list[Leg]
    exit_reason: str = ""  # "expiration", "stop_loss", "take_profit", "dte_exit"


@dataclass
class Portfolio:
    """Tracks open positions, closed trades, and equity curve."""

    initial_capital: float = 100_000.0
    cash: float = 100_000.0
    open_positions: list[Position] = field(default_factory=list)
    closed_trades: list[Trade] = field(default_factory=list)

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.open_positions)

    @property
    def equity(self) -> float:
        return self.cash + self.unrealized_pnl

    @property
    def net_dollar_delta(self) -> float:
        """Net dollar delta as fraction of equity."""
        total = 0.0
        for pos in self.open_positions:
            for leg in pos.legs:
                total += leg.delta * leg.sign * leg.quantity * 100
        return total / self.equity if self.equity > 0 else 0.0
