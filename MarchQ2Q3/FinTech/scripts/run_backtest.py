"""CLI entry point for running backtests."""

from __future__ import annotations

import argparse
from datetime import date

from src.backtest.engine import BacktestConfig, run_backtest
from src.backtest.reporting import compute_metrics, print_report
from src.backtest.strategies.vol_selling import VolSellingStrategy
from src.data.fetchers import get_fetcher
from src.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run options backtest")
    parser.add_argument("--ticker", default="AAPL", help="Ticker symbol")
    parser.add_argument("--start", default="2022-01-01", help="Start date")
    parser.add_argument("--end", default="2024-12-31", help="End date")
    parser.add_argument("--strategy", default="vol_selling", help="Strategy name")
    parser.add_argument("--capital", type=float, default=100_000, help="Initial capital")

    args = parser.parse_args()
    configure_logging()

    # Fetch data
    fetcher = get_fetcher()
    ohlcv = fetcher.get_ohlcv(args.ticker, args.start, args.end)

    # Select strategy
    if args.strategy == "vol_selling":
        strategy = VolSellingStrategy()
    else:
        raise ValueError(f"Unknown strategy: {args.strategy}")

    config = BacktestConfig(
        ticker=args.ticker,
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        initial_capital=args.capital,
    )

    portfolio, ledger = run_backtest(strategy, ohlcv, config)
    metrics = compute_metrics(portfolio, ledger)
    print_report(metrics)


if __name__ == "__main__":
    main()
