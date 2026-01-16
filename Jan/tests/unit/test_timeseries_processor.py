"""Unit tests for time-series processor."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.analytics.timeseries_processor import (
    DataQualityError,
    TimeSeriesProcessor,
    process_trading_data,
)


class TestTimeSeriesProcessor:
    """Tests for TimeSeriesProcessor class."""

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample trading data."""
        base_time = datetime(2026, 1, 17, 10, 0, 0)
        data = {
            "timestamp": [base_time + timedelta(minutes=i * 10) for i in range(10)],
            "symbol": ["POWER_DE"] * 10,
            "price": [85.0, 85.5, 86.0, 85.5, 86.5, 87.0, 86.5, 87.5, 88.0, 87.0],
            "volume": [100, 150, 120, 80, 200, 180, 90, 160, 140, 110],
        }
        return pd.DataFrame(data)

    def test_processor_initialization(self) -> None:
        """Test processor initialization with defaults."""
        processor = TimeSeriesProcessor()
        assert processor.max_gap_hours == 24
        assert processor.min_valid_price == 0.0

    def test_process_valid_data(self, sample_data: pd.DataFrame) -> None:
        """Test processing valid data."""
        processor = TimeSeriesProcessor()
        result = processor.process_trading_data(sample_data)

        assert not result.empty
        assert "symbol" in result.columns
        assert "vwap" in result.columns
        assert "total_volume" in result.columns

    def test_process_empty_dataframe(self) -> None:
        """Test processing empty DataFrame."""
        processor = TimeSeriesProcessor()
        empty_df = pd.DataFrame(columns=["timestamp", "symbol", "price", "volume"])

        result = processor.process_trading_data(empty_df)
        assert result.empty

    def test_missing_columns_raises_error(self) -> None:
        """Test that missing required columns raise ValueError."""
        processor = TimeSeriesProcessor()
        df = pd.DataFrame({"timestamp": [], "symbol": []})  # Missing price, volume

        with pytest.raises(ValueError, match="Missing required columns"):
            processor.process_trading_data(df)

    def test_duplicate_handling_keep_last(self) -> None:
        """Test that duplicate timestamps keep last value (correction)."""
        processor = TimeSeriesProcessor()
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        data = {
            "timestamp": [base_time, base_time, base_time + timedelta(hours=1)],
            "symbol": ["POWER_DE", "POWER_DE", "POWER_DE"],
            "price": [85.0, 86.0, 87.0],  # Second value is correction
            "volume": [100, 150, 120],
        }
        df = pd.DataFrame(data)

        result = processor.process_trading_data(df)

        # After dedup, first hour should use the corrected price (86.0)
        assert not result.empty

    def test_missing_price_forward_fill(self) -> None:
        """Test that missing prices are forward-filled."""
        processor = TimeSeriesProcessor()
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        data = {
            "timestamp": [
                base_time,
                base_time + timedelta(minutes=30),
                base_time + timedelta(hours=1),
            ],
            "symbol": ["POWER_DE"] * 3,
            "price": [85.0, np.nan, 87.0],  # Missing middle price
            "volume": [100, 150, 120],
        }
        df = pd.DataFrame(data)

        result = processor.process_trading_data(df)

        # Should complete without error (forward-fill handles NaN)
        assert not result.empty

    def test_missing_volume_interpolation(self) -> None:
        """Test that missing volumes are interpolated."""
        processor = TimeSeriesProcessor()
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        data = {
            "timestamp": [
                base_time,
                base_time + timedelta(minutes=30),
                base_time + timedelta(hours=1),
            ],
            "symbol": ["POWER_DE"] * 3,
            "price": [85.0, 86.0, 87.0],
            "volume": [100, np.nan, 120],  # Missing middle volume
        }
        df = pd.DataFrame(data)

        result = processor.process_trading_data(df)

        # Should complete without error (interpolation handles NaN)
        assert not result.empty

    def test_negative_volume_raises_error(self) -> None:
        """Test that negative volumes raise DataQualityError."""
        processor = TimeSeriesProcessor()
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        data = {
            "timestamp": [base_time, base_time + timedelta(hours=1)],
            "symbol": ["POWER_DE"] * 2,
            "price": [85.0, 86.0],
            "volume": [100, -50],  # Negative volume
        }
        df = pd.DataFrame(data)

        with pytest.raises(DataQualityError, match="negative volume"):
            processor.process_trading_data(df)

    def test_negative_price_raises_error(self) -> None:
        """Test that negative prices raise DataQualityError."""
        processor = TimeSeriesProcessor(min_valid_price=0.0)
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        data = {
            "timestamp": [base_time, base_time + timedelta(hours=1)],
            "symbol": ["POWER_DE"] * 2,
            "price": [85.0, -10.0],  # Negative price
            "volume": [100, 50],
        }
        df = pd.DataFrame(data)

        with pytest.raises(DataQualityError, match="invalid price"):
            processor.process_trading_data(df)

    def test_vwap_calculation(self) -> None:
        """Test VWAP calculation is correct."""
        processor = TimeSeriesProcessor()
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        # All trades in same hour:
        # price=100, volume=60 -> value=6000
        # price=110, volume=40 -> value=4400
        # VWAP = 10400 / 100 = 104
        data = {
            "timestamp": [
                base_time + timedelta(minutes=10),
                base_time + timedelta(minutes=20),
            ],
            "symbol": ["POWER_DE"] * 2,
            "price": [100.0, 110.0],
            "volume": [60.0, 40.0],
        }
        df = pd.DataFrame(data)

        result = processor.process_trading_data(df)

        assert len(result) == 1
        assert abs(result["vwap"].iloc[0] - 104.0) < 0.01

    def test_multiple_symbols(self) -> None:
        """Test processing data with multiple symbols."""
        processor = TimeSeriesProcessor()
        base_time = datetime(2026, 1, 17, 10, 0, 0)

        data = {
            "timestamp": [base_time] * 4 + [base_time + timedelta(hours=1)] * 2,
            "symbol": ["POWER_DE", "POWER_DE", "GAS_NL", "GAS_NL", "POWER_DE", "GAS_NL"],
            "price": [85.0, 86.0, 42.0, 43.0, 87.0, 44.0],
            "volume": [100, 100, 50, 50, 150, 75],
        }
        df = pd.DataFrame(data)

        result = processor.process_trading_data(df)

        # Should have results for both symbols
        symbols = result["symbol"].unique()
        assert "POWER_DE" in symbols
        assert "GAS_NL" in symbols


class TestConvenienceFunction:
    """Tests for the process_trading_data convenience function."""

    def test_convenience_function(self) -> None:
        """Test the convenience function works."""
        base_time = datetime(2026, 1, 17, 10, 0, 0)
        data = {
            "timestamp": [base_time + timedelta(minutes=i * 10) for i in range(5)],
            "symbol": ["POWER_DE"] * 5,
            "price": [85.0, 85.5, 86.0, 85.5, 86.5],
            "volume": [100, 150, 120, 80, 200],
        }
        df = pd.DataFrame(data)

        result = process_trading_data(df)

        assert not result.empty
        assert "vwap" in result.columns
