"""Price-based features: returns, vol, RSI, MACD, Bollinger, SMAs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd


def add_returns(df: pd.DataFrame, col: str = "close") -> pd.DataFrame:
    """Add log returns."""
    df = df.copy()
    df["log_return"] = np.log(df[col] / df[col].shift(1))
    df["pct_return"] = df[col].pct_change()
    return df


def add_realized_vol(df: pd.DataFrame, windows: list[int] | None = None) -> pd.DataFrame:
    """Add realized volatility at multiple windows (annualized)."""
    df = df.copy()
    if "log_return" not in df.columns:
        df = add_returns(df)
    for w in windows or [5, 20, 60]:
        df[f"rv_{w}d"] = df["log_return"].rolling(w).std() * np.sqrt(252)
    # Vol-of-vol proxy
    if "rv_5d" in df.columns and "rv_60d" in df.columns:
        df["rv_ratio_5_60"] = df["rv_5d"] / df["rv_60d"]
    return df


def add_sma(df: pd.DataFrame, windows: list[int] | None = None) -> pd.DataFrame:
    """Add simple moving averages."""
    df = df.copy()
    for w in windows or [20, 50]:
        df[f"sma_{w}"] = df["close"].rolling(w).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add Relative Strength Index."""
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - 100 / (1 + rs)
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Add MACD indicator."""
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def add_bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Add Bollinger Bands."""
    df = df.copy()
    sma = df["close"].rolling(window).mean()
    std = df["close"].rolling(window).std()
    df["bb_upper"] = sma + num_std * std
    df["bb_lower"] = sma - num_std * std
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    return df


def add_drawdown(df: pd.DataFrame) -> pd.DataFrame:
    """Add drawdown from rolling high-water mark."""
    df = df.copy()
    cummax = df["close"].cummax()
    df["drawdown"] = (df["close"] - cummax) / cummax
    return df


def build_price_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all price-based features."""
    df = add_returns(df)
    df = add_realized_vol(df)
    df = add_sma(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger(df)
    df = add_drawdown(df)
    return df
