"""Tests for feature engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.features.price_features import (
    add_bollinger,
    add_drawdown,
    add_macd,
    add_realized_vol,
    add_returns,
    add_rsi,
    add_sma,
    build_price_features,
)


def _make_ohlcv(n: int = 100) -> pd.DataFrame:
    """Create a simple OHLCV DataFrame for testing."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=n)
    closes = 185.0 + np.cumsum(rng.normal(0, 1.5, n))
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


class TestPriceFeatures:
    def test_add_returns(self) -> None:
        df = add_returns(_make_ohlcv())
        assert "log_return" in df.columns
        assert "pct_return" in df.columns

    def test_add_realized_vol(self) -> None:
        df = add_realized_vol(_make_ohlcv())
        assert "rv_5d" in df.columns
        assert "rv_20d" in df.columns
        assert "rv_60d" in df.columns
        assert "rv_ratio_5_60" in df.columns

    def test_add_sma(self) -> None:
        df = add_sma(_make_ohlcv())
        assert "sma_20" in df.columns
        assert "sma_50" in df.columns

    def test_add_rsi(self) -> None:
        df = add_rsi(_make_ohlcv())
        assert "rsi_14" in df.columns
        valid = df["rsi_14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_add_macd(self) -> None:
        df = add_macd(_make_ohlcv())
        assert "macd" in df.columns
        assert "macd_signal" in df.columns
        assert "macd_hist" in df.columns

    def test_add_bollinger(self) -> None:
        df = add_bollinger(_make_ohlcv())
        assert "bb_upper" in df.columns
        assert "bb_lower" in df.columns
        assert "bb_pct" in df.columns

    def test_add_drawdown(self) -> None:
        df = add_drawdown(_make_ohlcv())
        assert "drawdown" in df.columns
        assert (df["drawdown"].dropna() <= 0).all()

    def test_build_price_features(self) -> None:
        df = build_price_features(_make_ohlcv())
        expected = {
            "log_return",
            "pct_return",
            "rv_5d",
            "rv_20d",
            "rv_60d",
            "sma_20",
            "sma_50",
            "rsi_14",
            "macd",
            "bb_upper",
            "drawdown",
        }
        assert expected.issubset(set(df.columns))
