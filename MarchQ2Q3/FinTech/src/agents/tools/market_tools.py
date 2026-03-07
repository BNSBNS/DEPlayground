"""Market data tools for agents."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from src.data.fetchers import get_fetcher

T = TypeVar("T")


class ToolResult[T](BaseModel):
    """Structured result from any tool call."""

    success: bool
    data: T | None = None
    error: str | None = None


class MarketDataInput(BaseModel):
    ticker: str
    start: str
    end: str


class OptionsChainInput(BaseModel):
    ticker: str
    date: str | None = None


def get_market_data(inp: MarketDataInput) -> ToolResult[dict]:
    """Fetch OHLCV data for a ticker."""
    try:
        fetcher = get_fetcher()
        df = fetcher.get_ohlcv(inp.ticker, inp.start, inp.end)
        return ToolResult(
            success=True,
            data={
                "ticker": inp.ticker,
                "rows": len(df),
                "start": str(df["date"].min()),
                "end": str(df["date"].max()),
                "latest_close": float(df["close"].iloc[-1]),
                "period_return": float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100),
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def get_options_chain(inp: OptionsChainInput) -> ToolResult[dict]:
    """Fetch options chain for a ticker."""
    try:
        fetcher = get_fetcher()
        df = fetcher.get_options_chain(inp.ticker, inp.date)
        return ToolResult(
            success=True,
            data={
                "ticker": inp.ticker,
                "contracts": len(df),
                "strikes": sorted(df["strike"].unique().tolist()),
                "avg_implied_vol": float(df["implied_vol"].mean()),
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def get_technical_indicators(inp: MarketDataInput) -> ToolResult[dict]:
    """Compute basic technical indicators."""
    try:
        fetcher = get_fetcher()
        df = fetcher.get_ohlcv(inp.ticker, inp.start, inp.end)
        close = df["close"]

        sma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
        sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
        vol_20 = (
            float(close.pct_change().rolling(20).std().iloc[-1] * (252**0.5))
            if len(close) >= 21
            else None
        )

        rsi = None
        if len(close) >= 15:
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean().iloc[-1]
            if loss != 0:
                rsi = float(100 - 100 / (1 + gain / loss))

        return ToolResult(
            success=True,
            data={
                "ticker": inp.ticker,
                "latest_close": float(close.iloc[-1]),
                "sma_20": sma_20,
                "sma_50": sma_50,
                "realized_vol_20d": vol_20,
                "rsi_14": rsi,
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
