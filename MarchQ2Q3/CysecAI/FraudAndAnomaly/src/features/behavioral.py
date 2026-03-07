"""User behavioral feature engineering.

Rolling window features capturing user spending patterns and velocity.
Requires DataFrame sorted by timestamp.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.utils import rolling_nunique_by_group


def compute_behavioral_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add user behavioral features to the DataFrame."""
    df = df.copy().sort_values("timestamp").reset_index(drop=True)

    # Time since last transaction per user (seconds)
    df["time_since_last_tx"] = (
        df.groupby("user_id")["timestamp"].diff().dt.total_seconds().fillna(0.0)
    )

    # Per-user rolling window features
    rolling_cols = ["tx_count_1h", "tx_count_24h", "avg_amount_7d", "amount_deviation"]
    rolling_frames: list[pd.DataFrame] = []

    for _, group in df.groupby("user_id"):
        g = group.set_index("timestamp").sort_index()

        g["tx_count_1h"] = g["amount"].rolling("1h").count()
        g["tx_count_24h"] = g["amount"].rolling("24h").count()
        g["avg_amount_7d"] = g["amount"].rolling("7D").mean()

        # Amount deviation from expanding mean/std (shift avoids leakage)
        exp_mean = g["amount"].expanding().mean().shift(1)
        exp_std = g["amount"].expanding().std().shift(1).clip(lower=1.0)
        g["amount_deviation"] = ((g["amount"] - exp_mean) / exp_std).fillna(0.0)

        rolling_frames.append(g.reset_index()[["transaction_id", *rolling_cols]])

    # Merge rolling features back via transaction_id (avoids index alignment issues)
    rolling_df = pd.concat(rolling_frames, ignore_index=True)
    df = df.merge(rolling_df, on="transaction_id")

    # Unique merchants in 24h (custom rolling nunique)
    df["unique_merchants_24h"] = rolling_nunique_by_group(
        df, "user_id", "merchant_category", "timestamp", np.timedelta64(24, "h")
    )

    # Per-user category familiarity: 0 on first encounter of a category
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["is_new_category_for_user"] = (
        df.groupby(["user_id", "merchant_category"]).cumcount() == 0
    ).astype(int)

    return df
