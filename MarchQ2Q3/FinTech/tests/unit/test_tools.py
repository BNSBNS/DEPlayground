"""Tests for agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest

from src.agents.tools.market_tools import (
    MarketDataInput,
    get_market_data,
    get_technical_indicators,
)
from src.agents.tools.quant_tools import PriceOptionInput, price_option
from src.config import get_settings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create mock OHLCV data and configure env."""
    market_dir = tmp_path / "mock" / "market_data"
    market_dir.mkdir(parents=True)
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=60)
    closes = 185.0 + np.cumsum(rng.normal(0, 1.5, 60))
    ohlcv = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes - rng.uniform(0, 1, 60),
            "high": closes + rng.uniform(0.5, 2, 60),
            "low": closes - rng.uniform(0.5, 2, 60),
            "close": closes,
            "volume": rng.integers(50_000_000, 100_000_000, 60),
        }
    )
    ohlcv.to_parquet(market_dir / "AAPL.parquet", index=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


class TestMarketTools:
    def test_get_market_data(self, mock_data_dir: Path) -> None:  # noqa: ARG002
        result = get_market_data(
            MarketDataInput(ticker="AAPL", start="2024-01-01", end="2024-12-31")
        )
        assert result.success
        assert result.data is not None
        assert result.data["ticker"] == "AAPL"
        assert result.data["rows"] > 0

    def test_get_market_data_missing(self, mock_data_dir: Path) -> None:  # noqa: ARG002
        result = get_market_data(
            MarketDataInput(ticker="NONEXISTENT", start="2024-01-01", end="2024-12-31")
        )
        assert not result.success

    def test_get_technical_indicators(self, mock_data_dir: Path) -> None:  # noqa: ARG002
        result = get_technical_indicators(
            MarketDataInput(ticker="AAPL", start="2024-01-01", end="2024-12-31")
        )
        assert result.success
        assert result.data is not None
        assert "latest_close" in result.data


class TestQuantTools:
    def test_price_option(self) -> None:
        result = price_option(
            PriceOptionInput(
                spot=185.0,
                strike=185.0,
                time_to_expiry=30 / 365,
                volatility=0.25,
                option_type="call",
            )
        )
        assert result.success
        assert result.data is not None
        assert result.data["price"] > 0
        assert "delta" in result.data
        assert "gamma" in result.data
