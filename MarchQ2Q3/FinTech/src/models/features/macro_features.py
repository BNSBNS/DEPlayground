"""Macro features: yield curve, VIX transforms, CPI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd


def add_yield_curve_slope(
    df: pd.DataFrame, long_col: str = "DGS10", short_col: str = "DGS2"
) -> pd.DataFrame:
    """Add yield curve slope (10Y - 2Y) and its first difference."""
    df = df.copy()
    if long_col in df.columns and short_col in df.columns:
        df["yield_curve_slope"] = df[long_col] - df[short_col]
        df["yield_curve_slope_diff"] = df["yield_curve_slope"].diff()
    return df


def add_vix_features(df: pd.DataFrame, vix_col: str = "VIXCLS") -> pd.DataFrame:
    """Add VIX log-transform and percentile rank (stationary for HMM)."""
    df = df.copy()
    if vix_col in df.columns:
        df["log_vix"] = np.log(df[vix_col].clip(lower=1.0))
        df["vix_pct_rank"] = df[vix_col].rank(pct=True)
    return df


def add_fed_funds_features(df: pd.DataFrame, ff_col: str = "FEDFUNDS") -> pd.DataFrame:
    """Add fed funds rate change."""
    df = df.copy()
    if ff_col in df.columns:
        df["fed_funds_diff"] = df[ff_col].diff()
    return df


def build_macro_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build all macro features."""
    df = add_yield_curve_slope(df)
    df = add_vix_features(df)
    df = add_fed_funds_features(df)
    return df
