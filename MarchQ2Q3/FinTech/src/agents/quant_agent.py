"""Quant agent — market data, technical indicators, options analysis."""

from __future__ import annotations

from src.agents.tools.market_tools import (
    MarketDataInput,
    OptionsChainInput,
    get_market_data,
    get_options_chain,
    get_technical_indicators,
)
from src.logging import get_logger

logger = get_logger(__name__)


def run_quant(ticker: str, start: str = "2023-01-01", end: str = "2024-12-31") -> dict:
    """Run the quant agent: market data + technicals + options.

    Returns a quant report dict with market analysis.
    """
    report: dict = {"ticker": ticker, "market": None, "technicals": None, "options": None}

    # 1. Market data summary
    market_result = get_market_data(MarketDataInput(ticker=ticker, start=start, end=end))
    if market_result.success:
        report["market"] = market_result.data

    # 2. Technical indicators
    tech_result = get_technical_indicators(MarketDataInput(ticker=ticker, start=start, end=end))
    if tech_result.success:
        report["technicals"] = tech_result.data

    # 3. Options chain summary
    options_result = get_options_chain(OptionsChainInput(ticker=ticker))
    if options_result.success:
        report["options"] = options_result.data

    logger.info("quant_complete", ticker=ticker)
    return report
