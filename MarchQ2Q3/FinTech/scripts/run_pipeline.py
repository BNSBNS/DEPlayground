"""CLI entry point for the data pipeline."""

from __future__ import annotations

import argparse

from src.data.pipeline import run_pipeline
from src.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the data pipeline")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL"],
        help="Tickers to fetch",
    )
    parser.add_argument("--start", default="2022-01-01", help="Start date")
    parser.add_argument("--end", default="2024-12-31", help="End date")
    parser.add_argument(
        "--macro",
        nargs="*",
        default=None,
        help="Macro series IDs to fetch (e.g., DGS10 VIXCLS)",
    )

    args = parser.parse_args()
    configure_logging()

    run_pipeline(
        tickers=args.tickers,
        start=args.start,
        end=args.end,
        macro_series=args.macro,
    )


if __name__ == "__main__":
    main()
