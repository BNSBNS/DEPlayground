"""Feature engineering — pure function over a raw trade_aggregates DataFrame.

No I/O, no state, no side effects. Input is whatever the repository returned
from the database; output is a ``FeatureFrame`` ready for training or inference.

The feature families produced here match what the plan documents:

* Raw passthrough     - vwap, total_volume, trade_count, max_price, min_price
* Lags                - vwap_lag_{1,5,15,30,60}, volume_lag_{1,5,15}
* Rolling stats       - vwap_roll_mean / std over 5, 15, 60 minutes
* Log returns         - log_return_1, log_return_5, realized_vol_15
* Calendar (cyclical) - hour_sin, hour_cos, dow_sin, dow_cos, is_weekend
* Spread              - price_range = max_price - min_price
* LMP components      - lmp_energy, lmp_congestion, lmp_loss (nullable, filled 0)

Rows with NaN in any feature column are dropped — this is intentional; a
model must never train on missing lag features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ml.features.schema import TARGET_COLUMN, FeatureFrame

# Lag windows (in rows / minutes at the 1-minute aggregate cadence).
_VWAP_LAGS = (1, 5, 15, 30, 60)
_VOLUME_LAGS = (1, 5, 15)
_ROLL_WINDOWS = (5, 15, 60)


class FeatureBuilder:
    """Transforms raw trade_aggregates rows into a ``FeatureFrame``.

    Stateless. Safe to reuse across training and inference so that features
    are guaranteed identical at both times (the #1 source of silent bugs in
    real forecasting systems).
    """

    def build(self, raw: pd.DataFrame) -> FeatureFrame:
        """Build features from a raw DataFrame.

        Args:
            raw: DataFrame with at least the columns ``window_start``, ``vwap``,
                ``total_volume``, ``trade_count``, ``max_price``, ``min_price``.
                Optional: ``lmp_energy``, ``lmp_congestion``, ``lmp_loss``.

        Returns:
            A ``FeatureFrame`` with a datetime index and all engineered columns.
        """
        if raw.empty:
            raise ValueError("Cannot build features from an empty DataFrame.")

        df = raw.copy()
        df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
        df = df.sort_values("window_start").set_index("window_start")

        # Cast Decimal -> float so pandas/numpy/torch can use the values.
        numeric_cols = [
            "vwap",
            "total_volume",
            "trade_count",
            "max_price",
            "min_price",
            "lmp_energy",
            "lmp_congestion",
            "lmp_loss",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)

        # ---------------- Lag features ----------------
        for lag in _VWAP_LAGS:
            df[f"vwap_lag_{lag}"] = df["vwap"].shift(lag)
        for lag in _VOLUME_LAGS:
            df[f"volume_lag_{lag}"] = df["total_volume"].shift(lag)

        # ---------------- Rolling stats ----------------
        for w in _ROLL_WINDOWS:
            df[f"vwap_roll_mean_{w}"] = df["vwap"].rolling(window=w).mean()
            df[f"vwap_roll_std_{w}"] = df["vwap"].rolling(window=w).std()

        # ---------------- Log returns ----------------
        df["log_return_1"] = np.log(df["vwap"] / df["vwap"].shift(1))
        df["log_return_5"] = np.log(df["vwap"] / df["vwap"].shift(5))
        df["realized_vol_15"] = df["log_return_1"].rolling(window=15).std()

        # ---------------- Calendar (cyclical encoding) ----------------
        # ``df.index`` is a DatetimeIndex at this point — the `.hour` and
        # `.dayofweek` accessors only exist on that subclass, so help mypy.
        assert isinstance(df.index, pd.DatetimeIndex)
        hour = df.index.hour.to_numpy()
        dow = df.index.dayofweek.to_numpy()
        df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
        df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        df["is_weekend"] = (dow >= 5).astype(float)

        # ---------------- Spread ----------------
        df["price_range"] = df["max_price"] - df["min_price"]

        # ---------------- LMP components (optional, fill NaN with 0) ----------------
        for col in ("lmp_energy", "lmp_congestion", "lmp_loss"):
            if col not in df.columns:
                df[col] = 0.0
            df[col] = df[col].fillna(0.0)

        # ---------------- Finalize ----------------
        # Exclude non-numeric columns and the target from the feature set.
        _EXCLUDE = {TARGET_COLUMN, "window_end", "symbol"}
        feature_columns = tuple(col for col in df.columns if col not in _EXCLUDE)
        df = df.dropna(subset=[*list(feature_columns), TARGET_COLUMN])

        return FeatureFrame(data=df, feature_columns=feature_columns)
