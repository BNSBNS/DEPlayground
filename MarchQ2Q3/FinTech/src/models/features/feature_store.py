"""Feature store — build and query features with point-in-time safety."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.data.fetchers import get_fetcher
from src.logging import get_logger
from src.models.features.price_features import build_price_features

if TYPE_CHECKING:
    import pandas as pd

    from src.data.store import DataStore

    pass

logger = get_logger(__name__)


def build_features(
    ticker: str,
    start: str,
    end: str,
    store: DataStore | None = None,
) -> pd.DataFrame:
    """Build features for a ticker, ensuring point-in-time correctness.

    For each feature at date D, only data <= D is used.
    """
    fetcher = get_fetcher()
    df = fetcher.get_ohlcv(ticker, start, end)
    df = df.sort_values("date").reset_index(drop=True)

    # Price features (all use lookback only — point-in-time safe)
    df = build_price_features(df)

    # Check multicollinearity
    numeric_cols = df.select_dtypes(include="number").columns
    if len(numeric_cols) > 2:
        corr = df[numeric_cols].corr().abs()
        high_corr = []
        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                if corr.iloc[i, j] > 0.8:
                    high_corr.append((corr.columns[i], corr.columns[j], corr.iloc[i, j]))
        if high_corr:
            logger.warning(
                "high_correlation_detected",
                pairs=[(a, b, f"{c:.2f}") for a, b, c in high_corr[:5]],
            )

    if store:
        store.save(df, f"features/{ticker}")
        logger.info("features_saved", ticker=ticker, rows=len(df))

    return df
