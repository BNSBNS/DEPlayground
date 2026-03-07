"""Transaction-level feature engineering.

Features derived from individual transaction attributes.
No lookback windows needed — computed per-row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

ROUND_AMOUNTS = {500.0, 1000.0, 2000.0, 5000.0}


def compute_transaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add transaction-level features to the DataFrame."""
    df = df.copy().sort_values("timestamp").reset_index(drop=True)

    # Amount z-score (global)
    std = df["amount"].std()
    df["amount_zscore"] = (df["amount"] - df["amount"].mean()) / std if std > 0 else 0.0

    # Round amount indicator
    df["is_round_amount"] = df["amount"].isin(ROUND_AMOUNTS).astype(int)

    # Time features
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_night"] = ((df["hour_of_day"] >= 22) | (df["hour_of_day"] <= 5)).astype(int)

    # Merchant risk: expanding fraud rate per category, shifted to avoid leakage
    df["merchant_risk_score"] = (
        df.groupby("merchant_category")["is_fraud"]
        .transform(lambda s: s.expanding().mean().shift(1))
        .fillna(0.0)
    )

    return df
