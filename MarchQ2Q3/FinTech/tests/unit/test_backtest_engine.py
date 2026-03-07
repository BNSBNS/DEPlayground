"""Tests for the backtest engine."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestConfig, LedgerEntry, run_backtest
from src.backtest.models import Leg, Portfolio, Position
from src.backtest.reporting import bootstrap_sharpe, compute_metrics
from src.backtest.risk import RiskLimits, RiskManager
from src.backtest.strategies.vol_selling import VolSellingStrategy


def _make_ohlcv(n: int = 252) -> pd.DataFrame:
    """Create synthetic OHLCV data for backtest testing."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2023-01-02", periods=n)
    closes = 185.0 + np.cumsum(rng.normal(0, 1.5, n))
    closes = np.maximum(closes, 50.0)  # floor at $50
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes - rng.uniform(0, 1, n),
            "high": closes + rng.uniform(0.5, 2, n),
            "low": closes - rng.uniform(0.5, 2, n),
            "close": closes,
            "volume": rng.integers(50_000_000, 100_000_000, n),
        }
    )


class TestBacktestEngine:
    def test_runs_without_error(self) -> None:
        strategy = VolSellingStrategy(iv_threshold=0.10)  # low threshold to trigger trades
        ohlcv = _make_ohlcv()
        config = BacktestConfig(
            ticker="TEST",
            start=date(2023, 1, 2),
            end=date(2023, 12, 31),
        )
        portfolio, ledger = run_backtest(strategy, ohlcv, config)
        assert len(ledger) == len(ohlcv)
        assert portfolio.equity > 0

    def test_ledger_equity_positive(self) -> None:
        strategy = VolSellingStrategy(iv_threshold=0.10)
        config = BacktestConfig(ticker="TEST", start=date(2023, 1, 2), end=date(2023, 12, 31))
        _, ledger = run_backtest(strategy, _make_ohlcv(), config)
        # Equity should remain positive (no bankruptcy)
        assert all(e.equity > 0 for e in ledger)

    def test_no_trades_when_iv_low(self) -> None:
        strategy = VolSellingStrategy(iv_threshold=10.0)  # impossibly high
        config = BacktestConfig(ticker="TEST", start=date(2023, 1, 2), end=date(2023, 12, 31))
        portfolio, _ = run_backtest(strategy, _make_ohlcv(), config)
        assert len(portfolio.closed_trades) == 0


class TestRiskManager:
    def test_max_positions_enforced(self) -> None:
        rm = RiskManager(RiskLimits(max_positions=1))
        port = Portfolio()
        port.open_positions.append(
            Position(
                ticker="TEST",
                strategy="test",
                entry_date=date(2024, 1, 1),
                expiration=date(2024, 2, 1),
                legs=[Leg(strike=185.0, option_type="call", side="sell")],
            )
        )
        assert not rm.can_open_new(port)

    def test_transaction_costs(self) -> None:
        rm = RiskManager()
        pos = Position(
            ticker="TEST",
            strategy="iron_condor",
            entry_date=date(2024, 1, 1),
            expiration=date(2024, 2, 1),
            legs=[
                Leg(strike=175.0, option_type="put", side="buy"),
                Leg(strike=180.0, option_type="put", side="sell"),
                Leg(strike=190.0, option_type="call", side="sell"),
                Leg(strike=195.0, option_type="call", side="buy"),
            ],
        )
        cost = rm.transaction_cost(pos)
        assert cost > 0  # slippage + commission


class TestReporting:
    def test_bootstrap_sharpe(self) -> None:
        pnls = np.array([10, -5, 15, -3, 8, 12, -2, 7])
        low, mid, high = bootstrap_sharpe(pnls)
        assert low <= mid <= high

    def test_compute_metrics(self) -> None:
        portfolio = Portfolio()
        ledger = [
            LedgerEntry(
                date=date(2023, 1, 2),
                equity=100_000,
                cash=100_000,
                open_positions=0,
                unrealized_pnl=0,
                net_delta=0,
            ),
            LedgerEntry(
                date=date(2023, 12, 29),
                equity=105_000,
                cash=105_000,
                open_positions=0,
                unrealized_pnl=0,
                net_delta=0,
            ),
        ]
        metrics = compute_metrics(portfolio, ledger)
        assert metrics.max_drawdown <= 0
        assert metrics.cagr >= 0
