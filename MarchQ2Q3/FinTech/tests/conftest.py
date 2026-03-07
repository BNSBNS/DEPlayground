"""Shared test fixtures for financial data."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Sample OHLCV DataFrame for AAPL (5 trading days)."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    rng = np.random.default_rng(42)
    base = 185.0
    closes = base + np.cumsum(rng.normal(0, 1.5, 5))
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes - rng.uniform(0, 1, 5),
            "high": closes + rng.uniform(0.5, 2, 5),
            "low": closes - rng.uniform(0.5, 2, 5),
            "close": closes,
            "volume": rng.integers(50_000_000, 100_000_000, 5),
        }
    )


@pytest.fixture
def sample_options_chain() -> pd.DataFrame:
    """Sample options chain for a single ticker/expiration."""
    spot = 185.0
    strikes = np.arange(170.0, 200.0, 5.0)
    rows = []
    for K in strikes:
        for opt_type in ["call", "put"]:
            moneyness = K / spot
            # Rough synthetic IV with skew
            iv = 0.25 - 0.10 * (moneyness - 1.0) + 0.02 * (moneyness - 1.0) ** 2
            rows.append(
                {
                    "ticker": "AAPL",
                    "expiration": datetime(2024, 2, 16),
                    "strike": K,
                    "option_type": opt_type,
                    "bid": max(0.01, 5.0 - abs(K - spot) * 0.3),
                    "ask": max(0.05, 5.5 - abs(K - spot) * 0.3),
                    "last": max(0.03, 5.25 - abs(K - spot) * 0.3),
                    "volume": int(max(1, 1000 - abs(K - spot) * 50)),
                    "open_interest": int(max(10, 5000 - abs(K - spot) * 200)),
                    "implied_vol": max(0.05, iv),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def sample_trade() -> dict:
    """Sample options trade."""
    return {
        "ticker": "AAPL",
        "strategy": "iron_condor",
        "entry_date": datetime(2024, 1, 15),
        "expiration": datetime(2024, 2, 16),
        "legs": [
            {"strike": 175.0, "option_type": "put", "side": "buy", "quantity": 1},
            {"strike": 180.0, "option_type": "put", "side": "sell", "quantity": 1},
            {"strike": 190.0, "option_type": "call", "side": "sell", "quantity": 1},
            {"strike": 195.0, "option_type": "call", "side": "buy", "quantity": 1},
        ],
        "credit": 1.50,
    }
