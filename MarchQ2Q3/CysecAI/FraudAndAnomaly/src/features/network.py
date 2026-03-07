"""Network and device feature engineering.

Features based on device sharing, IP patterns, and geographic behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from src.features.utils import rolling_nunique_by_group

if TYPE_CHECKING:
    import pandas as pd


def _haversine_km(
    lat1: pd.Series,
    lon1: pd.Series,
    lat2: pd.Series,
    lon2: pd.Series,
) -> pd.Series:
    """Vectorized haversine distance in kilometers."""
    r = 6371.0
    lat1_r, lat2_r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return r * 2 * np.arcsin(np.sqrt(a))  # type: ignore[no-any-return]


def compute_network_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add network/device/geo features to the DataFrame."""
    df = df.copy()

    # Shared device count: unique users per device_id
    df["shared_device_count"] = df.groupby("device_id")["user_id"].transform("nunique")

    # Unique IPs in 24h per user
    df["unique_ips_24h"] = rolling_nunique_by_group(
        df, "user_id", "ip_address", "timestamp", np.timedelta64(24, "h")
    )

    # Per-user device novelty: 1 if user has never used this device before
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["is_new_device_for_user"] = (df.groupby(["user_id", "device_id"]).cumcount() == 0).astype(
        int
    )

    # Geo distance from "home" (user's first transaction location)
    home = (
        df.sort_values("timestamp")
        .groupby("user_id")[["geo_lat", "geo_lon"]]
        .first()
        .rename(columns={"geo_lat": "home_lat", "geo_lon": "home_lon"})
    )
    df = df.merge(home, on="user_id", how="left")
    df["geo_distance_from_home"] = _haversine_km(
        df["home_lat"], df["home_lon"], df["geo_lat"], df["geo_lon"]
    )
    df = df.drop(columns=["home_lat", "home_lon"])

    return df
