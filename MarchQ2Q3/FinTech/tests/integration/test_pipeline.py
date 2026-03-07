"""Integration tests for the data pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pandera.errors
import pytest

from src.config import get_settings
from src.data.pipeline import ohlcv_schema, run_ohlcv_pipeline, run_pipeline
from src.data.store import DataStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_data_dir(tmp_path: Path) -> Path:
    """Set up mock data for pipeline tests."""
    market_dir = tmp_path / "mock" / "market_data"
    market_dir.mkdir(parents=True)
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=10)
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

    macro_dir = tmp_path / "mock" / "macro"
    macro_dir.mkdir(parents=True)
    macro = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "value": rng.uniform(4.0, 5.0, 10),
        }
    )
    macro.to_parquet(macro_dir / "DGS10.parquet", index=False)

    return tmp_path


@pytest.fixture
def store(tmp_path: Path) -> DataStore:
    """DataStore in a temp directory (separate from mock data)."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return DataStore(data_dir=str(output_dir))


class TestOHLCVPipeline:
    def test_fetches_and_stores(
        self,
        mock_data_dir: Path,
        store: DataStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(mock_data_dir))
        get_settings.cache_clear()
        try:
            run_ohlcv_pipeline(["AAPL"], "2024-01-01", "2024-12-31", store=store)
            df = store.load("market_data/AAPL")
            assert len(df) > 0
            assert set(df.columns) >= {"date", "open", "high", "low", "close", "volume"}
        finally:
            get_settings.cache_clear()

    def test_stored_data_passes_schema(
        self,
        mock_data_dir: Path,
        store: DataStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(mock_data_dir))
        get_settings.cache_clear()
        try:
            run_ohlcv_pipeline(["AAPL"], "2024-01-01", "2024-12-31", store=store)
            df = store.load("market_data/AAPL")
            ohlcv_schema.validate(df)
        finally:
            get_settings.cache_clear()


class TestSchemaValidation:
    def test_rejects_negative_prices(self) -> None:
        bad_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "open": [-1.0],
                "high": [2.0],
                "low": [1.0],
                "close": [1.5],
                "volume": [100],
            }
        )
        with pytest.raises(pandera.errors.SchemaError):
            ohlcv_schema.validate(bad_df)

    def test_rejects_missing_columns(self) -> None:
        incomplete_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "close": [185.0],
            }
        )
        with pytest.raises(pandera.errors.SchemaError):
            ohlcv_schema.validate(incomplete_df)


class TestFullPipeline:
    def test_end_to_end(
        self,
        mock_data_dir: Path,
        store: DataStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(mock_data_dir))
        get_settings.cache_clear()
        try:
            run_pipeline(
                tickers=["AAPL"],
                start="2024-01-01",
                end="2024-12-31",
                macro_series=["DGS10"],
                store=store,
            )
            ohlcv = store.load("market_data/AAPL")
            macro = store.load("macro/DGS10")
            assert len(ohlcv) > 0
            assert len(macro) > 0
        finally:
            get_settings.cache_clear()
