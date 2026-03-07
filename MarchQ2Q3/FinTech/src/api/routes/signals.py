"""Signals endpoint — technical indicators for a ticker."""

from __future__ import annotations

from fastapi import APIRouter

from src.agents.tools.market_tools import MarketDataInput, get_technical_indicators

router = APIRouter(prefix="/api/v1", tags=["signals"])


@router.get("/signals/{ticker}")
def get_signals(ticker: str, start: str = "2023-01-01", end: str = "2024-12-31") -> dict:
    """Get technical signals for a ticker (sync — DuckDB is not async-safe)."""
    result = get_technical_indicators(MarketDataInput(ticker=ticker, start=start, end=end))
    if not result.success:
        return {"error": result.error}
    return result.data or {}
