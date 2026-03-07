"""Backtest reporting — metrics with bootstrap confidence intervals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.backtest.engine import LedgerEntry
    from src.backtest.models import Portfolio


@dataclass
class BacktestMetrics:
    """Summary metrics for a backtest run."""

    total_trades: int
    win_rate: float
    total_pnl: float
    sharpe: float
    sharpe_ci_low: float
    sharpe_ci_high: float
    sortino: float
    max_drawdown: float
    profit_factor: float
    cagr: float


def bootstrap_sharpe(trade_pnls: np.ndarray, n: int = 10000) -> tuple[float, float, float]:
    """Bootstrap Sharpe ratio with 95% CI."""
    if len(trade_pnls) < 2:
        return 0.0, 0.0, 0.0

    rng = np.random.default_rng(42)
    sharpes: list[float] = []
    for _ in range(n):
        sample = rng.choice(trade_pnls, size=len(trade_pnls), replace=True)
        std = sample.std()
        if std > 0:
            sharpes.append(float(sample.mean() / std * np.sqrt(252)))

    if not sharpes:
        return 0.0, 0.0, 0.0

    ci = np.percentile(sharpes, [2.5, 50, 97.5])
    return float(ci[0]), float(ci[1]), float(ci[2])


def compute_metrics(
    portfolio: Portfolio,
    ledger: list[LedgerEntry],
) -> BacktestMetrics:
    """Compute comprehensive backtest metrics."""
    trades = portfolio.closed_trades
    pnls = np.array([t.pnl for t in trades]) if trades else np.array([0.0])

    # Win rate
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls) if len(pnls) > 0 else 0.0

    # Profit factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe with bootstrap CI
    ci_low, sharpe, ci_high = bootstrap_sharpe(pnls)

    # Sortino (downside deviation)
    downside = pnls[pnls < 0]
    downside_std = downside.std() if len(downside) > 1 else 1.0
    sortino = float(pnls.mean() / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0

    # Max drawdown from equity curve
    equities = np.array([e.equity for e in ledger]) if ledger else np.array([100_000.0])
    peak = np.maximum.accumulate(equities)
    drawdowns = (equities - peak) / peak
    max_dd = float(drawdowns.min())

    # CAGR
    if len(ledger) >= 2:
        years = (ledger[-1].date - ledger[0].date).days / 365.25
        if years > 0 and equities[-1] > 0 and equities[0] > 0:
            cagr = float((equities[-1] / equities[0]) ** (1 / years) - 1)
        else:
            cagr = 0.0
    else:
        cagr = 0.0

    return BacktestMetrics(
        total_trades=len(trades),
        win_rate=win_rate,
        total_pnl=float(pnls.sum()),
        sharpe=sharpe,
        sharpe_ci_low=ci_low,
        sharpe_ci_high=ci_high,
        sortino=sortino,
        max_drawdown=max_dd,
        profit_factor=profit_factor,
        cagr=cagr,
    )


def print_report(metrics: BacktestMetrics) -> None:
    """Print a formatted backtest report."""
    print("\n" + "=" * 50)
    print("BACKTEST RESULTS")
    print("=" * 50)
    print(f"Total Trades:    {metrics.total_trades}")
    print(f"Win Rate:        {metrics.win_rate:.1%}")
    print(f"Total P&L:       ${metrics.total_pnl:,.2f}")
    print(
        f"Sharpe Ratio:    {metrics.sharpe:.2f}"
        f" [{metrics.sharpe_ci_low:.2f}, {metrics.sharpe_ci_high:.2f}] (95% CI)"
    )
    print(f"Sortino Ratio:   {metrics.sortino:.2f}")
    print(f"Max Drawdown:    {metrics.max_drawdown:.2%}")
    print(f"Profit Factor:   {metrics.profit_factor:.2f}")
    print(f"CAGR:            {metrics.cagr:.2%}")
    print("=" * 50)
