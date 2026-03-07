"""Live fetcher — real data from yfinance, FRED, etc."""

from __future__ import annotations

import pandas as pd

from src.data.fetchers.base import BaseFetcher


class LiveFetcher(BaseFetcher):
    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        import yfinance as yf  # noqa: PLC0415

        df = yf.download(ticker, start=start, end=end, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index().rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        if "adj_close" in df.columns:
            df["close"] = df["adj_close"]
            df = df.drop(columns=["adj_close"])

        df["date"] = pd.to_datetime(df["date"])
        return df

    def get_options_chain(self, ticker: str, date: str | None = None) -> pd.DataFrame:
        raise NotImplementedError("Live options chain not yet implemented")

    def get_macro(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        from fredapi import Fred  # noqa: PLC0415

        from src.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        fred = Fred(api_key=settings.FRED_API_KEY)
        data = fred.get_series(series_id, observation_start=start, observation_end=end)
        df = pd.DataFrame({"date": data.index, "value": data.values})
        df["date"] = pd.to_datetime(df["date"])
        return df.dropna().reset_index(drop=True)
