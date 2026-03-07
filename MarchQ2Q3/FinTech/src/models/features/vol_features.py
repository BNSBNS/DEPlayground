"""Volatility features: IV rank, IV-RV spread, term structure, skew."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd


def add_iv_rank(
    df: pd.DataFrame, iv_col: str = "implied_vol", min_window: int = 63
) -> pd.DataFrame:
    """Add IV rank using expanding window (min 63 days to avoid cold start)."""
    df = df.copy()
    iv = df[iv_col]
    rolling_min = iv.expanding(min_periods=min_window).min()
    rolling_max = iv.expanding(min_periods=min_window).max()
    denom = rolling_max - rolling_min
    df["iv_rank"] = np.where(denom > 0, (iv - rolling_min) / denom, np.nan)
    return df


def add_iv_rv_spread(
    df: pd.DataFrame, iv_col: str = "implied_vol", rv_col: str = "rv_20d"
) -> pd.DataFrame:
    """Add IV minus RV spread (vol risk premium proxy)."""
    df = df.copy()
    if iv_col in df.columns and rv_col in df.columns:
        df["iv_rv_spread"] = df[iv_col] - df[rv_col]
    return df


def add_put_call_skew(df: pd.DataFrame) -> pd.DataFrame:
    """Add put-call IV skew from options chain data.

    Expects df with 'option_type' and 'implied_vol' columns, grouped by date.
    """
    df = df.copy()
    if "option_type" not in df.columns or "implied_vol" not in df.columns:
        return df

    put_iv = df.loc[df["option_type"] == "put", "implied_vol"].mean()
    call_iv = df.loc[df["option_type"] == "call", "implied_vol"].mean()
    df["put_call_skew"] = put_iv - call_iv
    return df


def build_vol_features(
    price_df: pd.DataFrame,
    iv_col: str = "implied_vol",
) -> pd.DataFrame:
    """Build all volatility features on a price DataFrame with IV column."""
    df = price_df.copy()
    if iv_col in df.columns:
        df = add_iv_rank(df, iv_col)
        df = add_iv_rv_spread(df, iv_col)
    return df
