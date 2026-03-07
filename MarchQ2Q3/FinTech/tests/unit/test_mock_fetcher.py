"""Tests for fetcher interface and MockFetcher implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

from src.config import get_settings
from src.data.fetchers.base import BaseFetcher
from src.data.fetchers.mock_fetcher import MockFetcher

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_data_dir(tmp_path: Path) -> Path:
    """Create mock data directory with sample Parquet files."""
    # OHLCV data
    market_dir = tmp_path / "mock" / "market_data"
    market_dir.mkdir(parents=True)
    dates = pd.bdate_range("2024-01-02", periods=10)
    rng = np.random.default_rng(42)
    closes = 185.0 + np.cumsum(rng.normal(0, 1.5, 10))
    ohlcv = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes - rng.uniform(0, 1, 10),
            "high": closes + rng.uniform(0.5, 2, 10),
            "low": closes - rng.uniform(0.5, 2, 10),
            "close": closes,
            "volume": rng.integers(50_000_000, 100_000_000, 10),
        }
    )
    ohlcv.to_parquet(market_dir / "AAPL.parquet", index=False)

    # Options chain data
    options_dir = tmp_path / "mock" / "options_chains"
    options_dir.mkdir(parents=True)
    rows = []
    for K in np.arange(170.0, 200.0, 5.0):
        for opt_type in ["call", "put"]:
            rows.append(
                {
                    "ticker": "AAPL",
                    "date": datetime(2024, 1, 15),
                    "expiration": datetime(2024, 2, 16),
                    "strike": K,
                    "option_type": opt_type,
                    "bid": max(0.01, 5.0 - abs(K - 185) * 0.3),
                    "ask": max(0.05, 5.5 - abs(K - 185) * 0.3),
                    "last": max(0.03, 5.25 - abs(K - 185) * 0.3),
                    "volume": int(max(1, 1000 - abs(K - 185) * 50)),
                    "open_interest": int(max(10, 5000 - abs(K - 185) * 200)),
                    "implied_vol": 0.25,
                }
            )
    pd.DataFrame(rows).to_parquet(options_dir / "AAPL.parquet", index=False)

    # Macro data
    macro_dir = tmp_path / "mock" / "macro"
    macro_dir.mkdir(parents=True)
    macro_dates = pd.bdate_range("2024-01-02", periods=10)
    macro = pd.DataFrame(
        {
            "date": pd.to_datetime(macro_dates),
            "value": rng.uniform(4.0, 5.0, 10),
        }
    )
    macro.to_parquet(macro_dir / "DGS10.parquet", index=False)

    return tmp_path


@pytest.fixture
def fetcher(mock_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> MockFetcher:
    """MockFetcher pointed at temp data directory."""
    monkeypatch.setenv("DATA_DIR", str(mock_data_dir))
    # Clear settings cache so it picks up new env
    get_settings.cache_clear()
    f = MockFetcher()
    yield f
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Contract tests — schema checks that apply to any BaseFetcher
# ---------------------------------------------------------------------------


OHLCV_COLUMNS = {"date", "open", "high", "low", "close", "volume"}
OPTIONS_COLUMNS = {
    "ticker",
    "expiration",
    "strike",
    "option_type",
    "bid",
    "ask",
    "last",
    "volume",
    "open_interest",
    "implied_vol",
}
MACRO_COLUMNS = {"date", "value"}


class TestFetcherContract:
    """Tests that MockFetcher obeys the BaseFetcher contract."""

    def test_is_base_fetcher(self, fetcher: MockFetcher) -> None:
        assert isinstance(fetcher, BaseFetcher)

    def test_ohlcv_columns(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_ohlcv("AAPL", "2024-01-01", "2024-12-31")
        assert OHLCV_COLUMNS.issubset(set(df.columns))

    def test_ohlcv_dtypes(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_ohlcv("AAPL", "2024-01-01", "2024-12-31")
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert pd.api.types.is_float_dtype(df["close"])

    def test_ohlcv_not_empty(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_ohlcv("AAPL", "2024-01-01", "2024-12-31")
        assert len(df) > 0

    def test_ohlcv_date_filtering(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_ohlcv("AAPL", "2024-01-03", "2024-01-08")
        assert df["date"].min() >= pd.Timestamp("2024-01-03")
        assert df["date"].max() <= pd.Timestamp("2024-01-08")

    def test_ohlcv_missing_ticker_raises(self, fetcher: MockFetcher) -> None:
        with pytest.raises(FileNotFoundError):
            fetcher.get_ohlcv("NONEXISTENT", "2024-01-01", "2024-12-31")

    def test_options_chain_columns(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_options_chain("AAPL")
        assert OPTIONS_COLUMNS.issubset(set(df.columns))

    def test_options_chain_types(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_options_chain("AAPL")
        assert all(t in ("call", "put") for t in df["option_type"].unique())
        assert pd.api.types.is_float_dtype(df["strike"])

    def test_options_chain_date_filter(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_options_chain("AAPL", date="2024-01-15")
        assert len(df) > 0

    def test_options_chain_missing_ticker_raises(self, fetcher: MockFetcher) -> None:
        with pytest.raises(FileNotFoundError):
            fetcher.get_options_chain("NONEXISTENT")

    def test_macro_columns(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_macro("DGS10", "2024-01-01", "2024-12-31")
        assert MACRO_COLUMNS.issubset(set(df.columns))

    def test_macro_dtypes(self, fetcher: MockFetcher) -> None:
        df = fetcher.get_macro("DGS10", "2024-01-01", "2024-12-31")
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert pd.api.types.is_float_dtype(df["value"])

    def test_macro_missing_series_raises(self, fetcher: MockFetcher) -> None:
        with pytest.raises(FileNotFoundError):
            fetcher.get_macro("NONEXISTENT", "2024-01-01", "2024-12-31")
