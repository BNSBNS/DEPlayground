"""Financial time-series processing for trading data.

Question 8: Clean a time-series dataset of trading prices and volumes
with missing values and duplicates, then resample it to hourly VWAP.

This module implements production-grade time-series processing following
the Senior Engineer Guidance patterns:
- Prices: Forward-fill (prices behave like step functions)
- Volume: Interpolation (represents continuous physical processes)
- Duplicates: Keep last (later values are corrections)
"""

from decimal import Decimal
from typing import Literal

import numpy as np
import pandas as pd

from src.common.logging_config import get_logger

logger = get_logger(__name__)


class DataQualityError(Exception):
    """Raised when data quality validation fails."""

    pass


class TimeSeriesProcessor:
    """Production-grade time-series processor for trading data.

    Handles:
    - Duplicate timestamp handling (keep last as corrections)
    - Missing price data (forward-fill)
    - Missing volume data (time-based interpolation)
    - Resampling to hourly VWAP
    - Data quality validation
    """

    def __init__(
        self,
        *,
        max_gap_hours: int = 24,
        min_valid_price: float = 0.0,
        max_volume_change_pct: float = 1000.0,
    ) -> None:
        """Initialize the time-series processor.

        Args:
            max_gap_hours: Maximum gap to fill with interpolation.
            min_valid_price: Minimum valid price (reject negatives).
            max_volume_change_pct: Maximum allowed volume change percentage
                                  (for anomaly detection).
        """
        self.max_gap_hours = max_gap_hours
        self.min_valid_price = min_valid_price
        self.max_volume_change_pct = max_volume_change_pct

    def process_trading_data(
        self,
        df: pd.DataFrame,
        *,
        symbol_column: str = "symbol",
        timestamp_column: str = "timestamp",
        price_column: str = "price",
        volume_column: str = "volume",
    ) -> pd.DataFrame:
        """Clean and aggregate raw trading data to hourly VWAP.

        This is the main entry point following the Senior Engineer pattern.

        Args:
            df: Raw trading DataFrame with timestamp, symbol, price, volume.
            symbol_column: Name of the symbol column.
            timestamp_column: Name of the timestamp column.
            price_column: Name of the price column.
            volume_column: Name of the volume column.

        Returns:
            DataFrame with hourly VWAP per symbol.

        Raises:
            DataQualityError: If critical data quality issues are detected.
            ValueError: If required columns are missing.
        """
        # Validate input
        required_columns = [symbol_column, timestamp_column, price_column, volume_column]
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if df.empty:
            logger.warning("Empty DataFrame provided")
            return pd.DataFrame(columns=["symbol", "hour", "vwap", "total_volume"])

        logger.info(
            "Processing trading data",
            rows=len(df),
            symbols=df[symbol_column].nunique(),
        )

        # Standardize column names
        df = df.rename(columns={
            timestamp_column: "timestamp",
            symbol_column: "symbol",
            price_column: "price",
            volume_column: "volume",
        })

        # Process each symbol separately
        results = []
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol].copy()
            processed = self._process_symbol(symbol_df, symbol)
            if not processed.empty:
                results.append(processed)

        if not results:
            logger.warning("No valid data after processing")
            return pd.DataFrame(columns=["symbol", "hour", "vwap", "total_volume"])

        result = pd.concat(results, ignore_index=True)

        logger.info(
            "Processing complete",
            output_rows=len(result),
            symbols=result["symbol"].nunique(),
        )

        return result

    def _process_symbol(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Process data for a single symbol.

        Args:
            df: DataFrame containing only one symbol's data.
            symbol: The symbol being processed.

        Returns:
            DataFrame with hourly VWAP for this symbol.
        """
        logger.debug(f"Processing symbol {symbol}", rows=len(df))

        # Step 1: Handle duplicates (keep last - later values are corrections)
        df = self._handle_duplicates(df)

        # Step 2: Set timestamp as index and sort
        df = df.set_index("timestamp").sort_index()

        # Step 3: Handle missing data by type
        df = self._handle_missing_data(df)

        # Step 4: Validate data quality
        self._validate_data(df, symbol)

        # Step 5: Compute hourly VWAP
        hourly = self._compute_hourly_vwap(df)

        # Add symbol back
        hourly["symbol"] = symbol

        return hourly.reset_index()

    def _handle_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle duplicate timestamps.

        Later values are treated as corrections to earlier values.

        Args:
            df: DataFrame potentially containing duplicates.

        Returns:
            DataFrame with duplicates removed (keeping last).
        """
        initial_rows = len(df)

        # Sort by timestamp to ensure "last" means chronologically last
        df = df.sort_values("timestamp")

        # Keep last occurrence (corrections override originals)
        df = df.drop_duplicates(subset=["timestamp"], keep="last")

        removed = initial_rows - len(df)
        if removed > 0:
            logger.info(
                "Removed duplicate timestamps",
                removed=removed,
                kept=len(df),
            )

        return df

    def _handle_missing_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values appropriately by data type.

        Following Senior Engineer Guidance:
        - Prices: Forward-fill (step function behavior)
        - Volume: Time-based interpolation (continuous process)

        Args:
            df: DataFrame with timestamp index.

        Returns:
            DataFrame with missing values handled.
        """
        # Count missing before
        price_missing = df["price"].isna().sum()
        volume_missing = df["volume"].isna().sum()

        # Forward-fill prices (prices persist until changed)
        df["price"] = df["price"].ffill()

        # Backward-fill any remaining prices at the start
        df["price"] = df["price"].bfill()

        # Interpolate volume (time-based for continuous processes)
        df["volume"] = df["volume"].interpolate(method="time")

        # Fill any remaining volume NaNs with 0
        df["volume"] = df["volume"].fillna(0)

        if price_missing > 0 or volume_missing > 0:
            logger.info(
                "Handled missing values",
                price_filled=price_missing,
                volume_interpolated=volume_missing,
            )

        return df

    def _validate_data(self, df: pd.DataFrame, symbol: str) -> None:
        """Validate data quality after processing.

        Args:
            df: Processed DataFrame.
            symbol: Symbol for error messages.

        Raises:
            DataQualityError: If critical issues are detected.
        """
        # Check for negative volumes
        if (df["volume"] < 0).any():
            neg_count = (df["volume"] < 0).sum()
            raise DataQualityError(
                f"Critical error: {neg_count} negative volume values detected for {symbol}"
            )

        # Check for negative prices
        if (df["price"] < self.min_valid_price).any():
            neg_count = (df["price"] < self.min_valid_price).sum()
            raise DataQualityError(
                f"Critical error: {neg_count} invalid price values detected for {symbol}"
            )

        # Check for remaining NaN values
        if df.isna().any().any():
            logger.warning(
                "Remaining NaN values after processing",
                symbol=symbol,
                price_nan=df["price"].isna().sum(),
                volume_nan=df["volume"].isna().sum(),
            )

        # Anomaly detection: extreme volume changes
        if len(df) > 1:
            volume_pct_change = df["volume"].pct_change().abs()
            extreme_changes = (volume_pct_change > self.max_volume_change_pct / 100).sum()
            if extreme_changes > 0:
                logger.warning(
                    "Extreme volume changes detected",
                    symbol=symbol,
                    count=extreme_changes,
                    max_change_pct=float(volume_pct_change.max() * 100),
                )

    def _compute_hourly_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute hourly VWAP from tick data.

        VWAP = sum(price * volume) / sum(volume)

        Args:
            df: DataFrame with timestamp index, price, volume columns.

        Returns:
            DataFrame with hourly VWAP and total volume.
        """
        # Compute value (price * volume) for VWAP calculation
        df = df.copy()
        df["value"] = df["price"] * df["volume"]

        # Resample to hourly
        hourly = df.resample("1h").agg({
            "value": "sum",
            "volume": "sum",
            "price": ["first", "last", "max", "min", "count"],
        })

        # Flatten column names
        hourly.columns = [
            "total_value",
            "total_volume",
            "open_price",
            "close_price",
            "high_price",
            "low_price",
            "trade_count",
        ]

        # Calculate VWAP
        hourly["vwap"] = hourly["total_value"] / hourly["total_volume"].replace(0, np.nan)

        # Fill VWAP where volume is 0 with previous value (no trades = price unchanged)
        hourly["vwap"] = hourly["vwap"].ffill()

        # Rename index
        hourly.index.name = "hour"

        # Select output columns
        result = hourly[["vwap", "total_volume", "trade_count", "high_price", "low_price"]].copy()

        # Drop rows with all NaN (no data in hour)
        result = result.dropna(subset=["vwap"])

        return result


def process_trading_data(
    df: pd.DataFrame,
    *,
    symbol_column: str = "symbol",
    timestamp_column: str = "timestamp",
    price_column: str = "price",
    volume_column: str = "volume",
) -> pd.DataFrame:
    """Convenience function for processing trading data.

    This is the simplified interface matching the Senior Engineer example.

    Args:
        df: Raw trading DataFrame.
        symbol_column: Name of symbol column.
        timestamp_column: Name of timestamp column.
        price_column: Name of price column.
        volume_column: Name of volume column.

    Returns:
        DataFrame with hourly VWAP per symbol.
    """
    processor = TimeSeriesProcessor()
    return processor.process_trading_data(
        df,
        symbol_column=symbol_column,
        timestamp_column=timestamp_column,
        price_column=price_column,
        volume_column=volume_column,
    )
