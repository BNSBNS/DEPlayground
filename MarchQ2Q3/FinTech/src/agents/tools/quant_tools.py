"""Quantitative tools for agents — options pricing, signals."""

from __future__ import annotations

from pydantic import BaseModel

from src.agents.tools.market_tools import ToolResult
from src.models.options_pricer import bs_price, delta, gamma, implied_vol, theta, vega


class PriceOptionInput(BaseModel):
    spot: float
    strike: float
    time_to_expiry: float  # in years
    risk_free_rate: float = 0.05
    volatility: float = 0.25
    option_type: str = "call"
    dividend_yield: float = 0.0


class ImpliedVolInput(BaseModel):
    market_price: float
    spot: float
    strike: float
    time_to_expiry: float
    risk_free_rate: float = 0.05
    option_type: str = "call"
    dividend_yield: float = 0.0


def price_option(inp: PriceOptionInput) -> ToolResult[dict]:
    """Price an option using Black-Scholes with full greeks."""
    try:
        price = bs_price(
            inp.spot,
            inp.strike,
            inp.time_to_expiry,
            inp.risk_free_rate,
            inp.volatility,
            inp.option_type,
            inp.dividend_yield,
        )
        d = delta(
            inp.spot,
            inp.strike,
            inp.time_to_expiry,
            inp.risk_free_rate,
            inp.volatility,
            inp.option_type,
            inp.dividend_yield,
        )
        g = gamma(
            inp.spot,
            inp.strike,
            inp.time_to_expiry,
            inp.risk_free_rate,
            inp.volatility,
            inp.dividend_yield,
        )
        t = theta(
            inp.spot,
            inp.strike,
            inp.time_to_expiry,
            inp.risk_free_rate,
            inp.volatility,
            inp.option_type,
            inp.dividend_yield,
        )
        v = vega(
            inp.spot,
            inp.strike,
            inp.time_to_expiry,
            inp.risk_free_rate,
            inp.volatility,
            inp.dividend_yield,
        )
        return ToolResult(
            success=True,
            data={
                "price": round(price, 4),
                "delta": round(d, 4),
                "gamma": round(g, 6),
                "theta": round(t, 4),
                "vega": round(v, 4),
                "option_type": inp.option_type,
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def compute_implied_vol(inp: ImpliedVolInput) -> ToolResult[dict]:
    """Compute implied volatility from market price."""
    try:
        iv = implied_vol(
            inp.market_price,
            inp.spot,
            inp.strike,
            inp.time_to_expiry,
            inp.risk_free_rate,
            inp.option_type,
            inp.dividend_yield,
        )
        return ToolResult(
            success=True,
            data={
                "implied_vol": round(iv, 6),
                "market_price": inp.market_price,
                "option_type": inp.option_type,
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
