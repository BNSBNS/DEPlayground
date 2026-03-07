"""Walk-forward backtest simulation engine.

The simulation iterates one trading day at a time.
On each day: reprice open positions -> check exits -> risk gate ->
generate signals -> fill -> record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from src.backtest.models import Portfolio, Trade
from src.backtest.pricer import reprice_leg
from src.backtest.risk import RiskLimits, RiskManager
from src.logging import get_logger

if TYPE_CHECKING:
    from datetime import date

    import pandas as pd

    from src.backtest.strategies.base import BaseStrategy

logger = get_logger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    ticker: str
    start: date
    end: date
    initial_capital: float = 100_000.0
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    risk_free_rate: float = 0.05


@dataclass
class LedgerEntry:
    """Daily snapshot of portfolio state."""

    date: date
    equity: float
    cash: float
    open_positions: int
    unrealized_pnl: float
    net_delta: float


def run_backtest(
    strategy: BaseStrategy,
    ohlcv: pd.DataFrame,
    config: BacktestConfig,
) -> tuple[Portfolio, list[LedgerEntry]]:
    """Run a walk-forward backtest.

    Args:
        strategy: Strategy instance that generates signals and exit rules
        ohlcv: DataFrame with date, open, high, low, close, volume columns
        config: Backtest configuration

    Returns:
        (portfolio, ledger) — final portfolio state and daily equity snapshots
    """
    rng = np.random.default_rng(42)
    risk_mgr = RiskManager(config.risk_limits)
    portfolio = Portfolio(
        initial_capital=config.initial_capital,
        cash=config.initial_capital,
    )
    ledger: list[LedgerEntry] = []

    # Compute a simple rolling IV proxy from realized vol
    ohlcv = ohlcv.sort_values("date").reset_index(drop=True)
    ohlcv["log_ret"] = np.log(ohlcv["close"] / ohlcv["close"].shift(1))
    ohlcv["rv_20"] = ohlcv["log_ret"].rolling(20).std() * np.sqrt(252)
    ohlcv["rv_20"] = ohlcv["rv_20"].fillna(0.25)

    for _, row in ohlcv.iterrows():
        current_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        spot = float(row["close"])
        iv = float(row["rv_20"])

        # Step 1: Mark-to-market — reprice all open positions via BS
        for pos in portfolio.open_positions:
            dte = pos.days_to_expiry(current_date)
            T = max(dte / 252, 1e-6)
            for leg in pos.legs:
                price, delta = reprice_leg(
                    spot,
                    leg.strike,
                    T,
                    config.risk_free_rate,
                    iv,
                    leg.option_type,
                    rng=rng,
                )
                leg.current_price = price
                leg.current_iv = iv
                leg.delta = delta

        # Step 2: Check exits
        to_close: list[int] = []
        for i, pos in enumerate(portfolio.open_positions):
            exit_reason = strategy.should_exit(pos, current_date, spot, iv)
            if pos.days_to_expiry(current_date) <= 0:
                exit_reason = "expiration"
            if exit_reason:
                # Close position
                exit_debit = sum(
                    leg.sign * leg.current_price * leg.quantity * 100 for leg in pos.legs
                )
                pnl = pos.unrealized_pnl - risk_mgr.transaction_cost(pos)
                portfolio.cash += pnl
                portfolio.closed_trades.append(
                    Trade(
                        ticker=config.ticker,
                        strategy=pos.strategy,
                        entry_date=pos.entry_date,
                        exit_date=current_date,
                        entry_credit=pos.entry_credit,
                        exit_debit=exit_debit,
                        pnl=pnl,
                        legs=pos.legs,
                        exit_reason=exit_reason,
                    )
                )
                to_close.append(i)

        # Remove closed positions (reverse order to preserve indices)
        for i in sorted(to_close, reverse=True):
            portfolio.open_positions.pop(i)

        # Step 3: Risk gate
        if not risk_mgr.can_open_new(portfolio):
            pass  # Skip signal generation
        else:
            # Step 4: Generate new signals
            signals = strategy.generate_signals(current_date, spot, iv)

            # Step 5: Fill orders
            for pos in signals:
                pos.ticker = config.ticker
                if risk_mgr.approve(pos, portfolio):
                    cost = risk_mgr.transaction_cost(pos)
                    portfolio.cash -= cost
                    portfolio.open_positions.append(pos)

        # Step 6: Record daily snapshot
        ledger.append(
            LedgerEntry(
                date=current_date,
                equity=portfolio.equity,
                cash=portfolio.cash,
                open_positions=len(portfolio.open_positions),
                unrealized_pnl=portfolio.unrealized_pnl,
                net_delta=portfolio.net_dollar_delta,
            )
        )

    logger.info(
        "backtest_complete",
        trades=len(portfolio.closed_trades),
        final_equity=f"{portfolio.equity:.2f}",
    )
    return portfolio, ledger
