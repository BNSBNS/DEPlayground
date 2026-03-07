"""Tests for transaction data preprocessor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from src.data.preprocessor import (
    encode_categoricals,
    handle_missing_values,
    log_transform_amount,
    preprocess,
    transactions_to_dataframe,
)

if TYPE_CHECKING:
    from src.data.generator import Transaction


class TestTransactionsToDataframe:
    """Test conversion from Transaction models to DataFrame."""

    def test_correct_shape(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        assert len(df) == len(sample_transactions)
        assert isinstance(df, pd.DataFrame)

    def test_amount_is_float(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        assert df["amount"].dtype == np.float64

    def test_preserves_fields(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        required = {
            "transaction_id",
            "user_id",
            "amount",
            "merchant_category",
            "timestamp",
            "device_id",
            "ip_address",
            "geo_lat",
            "geo_lon",
            "is_fraud",
            "fraud_strategy",
        }
        assert required.issubset(set(df.columns))


class TestHandleMissingValues:
    """Test missing value handling."""

    def test_fills_numeric_nan(self) -> None:
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0], "b": ["x", "y", "z"]})
        result = handle_missing_values(df)
        assert not result["a"].isna().any()

    def test_fills_string_none(self) -> None:
        df = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", None]})
        result = handle_missing_values(df)
        assert result["b"].iloc[1] == "unknown"

    def test_no_change_when_clean(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        result = handle_missing_values(df)
        assert len(result) == len(df)
        assert not result.isna().any().any()


class TestEncodeCategoricals:
    """Test categorical encoding."""

    def test_adds_category_code(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        result = encode_categoricals(df)
        assert "merchant_category_code" in result.columns

    def test_codes_are_integers(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        result = encode_categoricals(df)
        assert np.issubdtype(result["merchant_category_code"].dtype, np.integer)


class TestLogTransform:
    """Test log transformation."""

    def test_adds_log_column(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        result = log_transform_amount(df)
        assert "amount_log" in result.columns

    def test_log_values_positive(self, sample_transactions: list[Transaction]) -> None:
        df = transactions_to_dataframe(sample_transactions)
        result = log_transform_amount(df)
        assert (result["amount_log"] >= 0).all()


class TestPreprocess:
    """Test full preprocessing pipeline."""

    def test_full_pipeline(self, sample_transactions: list[Transaction]) -> None:
        df = preprocess(sample_transactions)
        assert "merchant_category_code" in df.columns
        assert "amount_log" in df.columns
        assert len(df) == len(sample_transactions)

    def test_no_missing_values(self, sample_transactions: list[Transaction]) -> None:
        df = preprocess(sample_transactions)
        # Exclude fraud_strategy which is legitimately None for non-fraud
        check_cols = [c for c in df.columns if c != "fraud_strategy"]
        assert not df[check_cols].isna().any().any()
