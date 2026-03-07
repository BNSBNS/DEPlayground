"""Base fetcher interface (ABC)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class BaseFetcher(ABC):
    """Abstract interface for all data fetchers.

    Implementations must return DataFrames with consistent schemas:
    - get_ohlcv: date, open, high, low, close, volume
    - get_options_chain: ticker, date, expiration, strike, option_type, bid, ask, implied_vol, ...
    - get_macro: date, value
    """

    @abstractmethod
    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV data for a ticker."""

    @abstractmethod
    def get_options_chain(self, ticker: str, date: str | None = None) -> pd.DataFrame:
        """Fetch options chain for a ticker."""

    @abstractmethod
    def get_macro(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        """Fetch macro data series (e.g., FRED)."""
