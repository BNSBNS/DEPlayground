"""Data pipeline — fetch, validate, and store market data."""

from __future__ import annotations

import pandera.pandas as pa

from src.data.fetchers import get_fetcher
from src.data.store import DataStore
from src.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pandera schemas for data validation at pipeline boundaries
# ---------------------------------------------------------------------------

ohlcv_schema = pa.DataFrameSchema(
    {
        "date": pa.Column("datetime64[ns]"),
        "open": pa.Column(float, pa.Check.gt(0)),
        "high": pa.Column(float, pa.Check.gt(0)),
        "low": pa.Column(float, pa.Check.gt(0)),
        "close": pa.Column(float, pa.Check.gt(0)),
        "volume": pa.Column(int, pa.Check.ge(0)),
    },
    coerce=True,
)

macro_schema = pa.DataFrameSchema(
    {
        "date": pa.Column("datetime64[ns]"),
        "value": pa.Column(float),
    },
    coerce=True,
)


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def run_ohlcv_pipeline(
    tickers: list[str],
    start: str,
    end: str,
    store: DataStore | None = None,
) -> None:
    """Fetch, validate, and store OHLCV data for each ticker."""
    fetcher = get_fetcher()
    if store is None:
        store = DataStore()

    for ticker in tickers:
        logger.info("fetching_ohlcv", ticker=ticker, start=start, end=end)
        df = fetcher.get_ohlcv(ticker, start, end)
        ohlcv_schema.validate(df)
        store.save(df, f"market_data/{ticker}")
        logger.info("saved_ohlcv", ticker=ticker, rows=len(df))


def run_macro_pipeline(
    series_ids: list[str],
    start: str,
    end: str,
    store: DataStore | None = None,
) -> None:
    """Fetch, validate, and store macro data for each series."""
    fetcher = get_fetcher()
    if store is None:
        store = DataStore()

    for series_id in series_ids:
        logger.info("fetching_macro", series_id=series_id, start=start, end=end)
        df = fetcher.get_macro(series_id, start, end)
        macro_schema.validate(df)
        store.save(df, f"macro/{series_id}")
        logger.info("saved_macro", series_id=series_id, rows=len(df))


def run_pipeline(
    tickers: list[str],
    start: str,
    end: str,
    macro_series: list[str] | None = None,
    store: DataStore | None = None,
) -> None:
    """Run the full data pipeline (OHLCV + macro)."""
    if store is None:
        store = DataStore()

    run_ohlcv_pipeline(tickers, start, end, store=store)

    if macro_series:
        run_macro_pipeline(macro_series, start, end, store=store)

    logger.info("pipeline_complete", tickers=tickers, macro_series=macro_series)
