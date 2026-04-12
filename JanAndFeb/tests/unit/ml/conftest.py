"""Fixtures shared by ML unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def raw_aggregates() -> pd.DataFrame:
    """Synthetic trade_aggregates with a deterministic sine-wave price.

    Produces one row per minute for 8 hours (480 rows) — enough to survive
    the 60-minute rolling features and the walk-forward splitter's default
    ``min_train_rows``.
    """
    rng = np.random.default_rng(42)
    n = 480
    start = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    times = [start + timedelta(minutes=i) for i in range(n)]

    # Gentle sine wave + noise so features have signal to learn.
    t = np.arange(n)
    base = 50.0 + 5.0 * np.sin(2 * np.pi * t / 60) + rng.normal(0, 0.2, n)
    volume = 100.0 + rng.normal(0, 5.0, n).clip(min=1.0)

    return pd.DataFrame(
        {
            "symbol": "POWER_DE",
            "window_start": times,
            "window_end": [ts + timedelta(minutes=1) for ts in times],
            "vwap": base,
            "total_volume": volume,
            "trade_count": rng.integers(1, 20, n),
            "max_price": base + 0.5,
            "min_price": base - 0.5,
            "lmp_energy": base * 0.9,
            "lmp_congestion": rng.normal(0, 0.1, n),
            "lmp_loss": rng.normal(0, 0.05, n),
        }
    )
