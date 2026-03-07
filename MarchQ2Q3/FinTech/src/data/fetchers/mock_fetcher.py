"""Mock fetcher — reads from data/mock/ directory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import get_settings
from src.data.fetchers.base import BaseFetcher


class MockFetcher(BaseFetcher):
    def __init__(self) -> None:
        settings = get_settings()
        self.data_dir = Path(settings.DATA_DIR) / "mock"

    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        path = self.data_dir / "market_data" / f"{ticker}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"No mock OHLCV data for {ticker}")

        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= start) & (df["date"] <= end)
        return df.loc[mask].reset_index(drop=True)

    def get_options_chain(self, ticker: str, date: str | None = None) -> pd.DataFrame:
        path = self.data_dir / "options_chains" / f"{ticker}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"No mock options data for {ticker}")

        df = pd.read_parquet(path)
        if date is not None:
            df["date"] = pd.to_datetime(df["date"])
            df = df[df["date"] == pd.Timestamp(date)]
        return df.reset_index(drop=True)

    def get_macro(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        path = self.data_dir / "macro" / f"{series_id}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"No mock macro data for {series_id}")

        df = pd.read_parquet(path)
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"] >= start) & (df["date"] <= end)
        return df.loc[mask].reset_index(drop=True)
