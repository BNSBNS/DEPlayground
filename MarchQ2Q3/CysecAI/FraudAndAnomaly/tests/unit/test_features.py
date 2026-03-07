"""Tests for feature engineering modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import pandas as pd

from src.data.preprocessor import preprocess
from src.features.behavioral import compute_behavioral_features
from src.features.network import compute_network_features
from src.features.pipeline import FeaturePipeline
from src.features.transaction import compute_transaction_features

if TYPE_CHECKING:
    from src.data.generator import Transaction


class TestTransactionFeatures:
    """Test transaction-level features."""

    @pytest.fixture()
    def tx_df(self, sample_transactions: list[Transaction]) -> pd.DataFrame:
        return compute_transaction_features(preprocess(sample_transactions))

    def test_amount_zscore_centered(self, tx_df: pd.DataFrame) -> None:
        assert abs(tx_df["amount_zscore"].mean()) < 0.01

    def test_is_round_amount_binary(self, tx_df: pd.DataFrame) -> None:
        assert set(tx_df["is_round_amount"].unique()).issubset({0, 1})

    def test_hour_range(self, tx_df: pd.DataFrame) -> None:
        assert tx_df["hour_of_day"].between(0, 23).all()

    def test_day_range(self, tx_df: pd.DataFrame) -> None:
        assert tx_df["day_of_week"].between(0, 6).all()

    def test_weekend_binary(self, tx_df: pd.DataFrame) -> None:
        assert set(tx_df["is_weekend"].unique()).issubset({0, 1})

    def test_night_binary(self, tx_df: pd.DataFrame) -> None:
        assert set(tx_df["is_night"].unique()).issubset({0, 1})

    def test_merchant_risk_no_future_leakage(self, tx_df: pd.DataFrame) -> None:
        """First tx per category has risk 0 (no prior data to learn from)."""
        assert tx_df["merchant_risk_score"].between(0.0, 1.0).all()
        for cat in tx_df["merchant_category"].unique():
            first_idx = tx_df[tx_df["merchant_category"] == cat].index[0]
            assert tx_df.loc[first_idx, "merchant_risk_score"] == 0.0


class TestBehavioralFeatures:
    """Test user behavioral features."""

    @pytest.fixture()
    def beh_df(self, sample_transactions: list[Transaction]) -> pd.DataFrame:
        df = compute_transaction_features(preprocess(sample_transactions))
        return compute_behavioral_features(df)

    def test_time_since_last_non_negative(self, beh_df: pd.DataFrame) -> None:
        assert (beh_df["time_since_last_tx"] >= 0).all()

    def test_tx_counts_at_least_one(self, beh_df: pd.DataFrame) -> None:
        assert (beh_df["tx_count_1h"] >= 1).all()
        assert (beh_df["tx_count_24h"] >= 1).all()

    def test_avg_amount_positive(self, beh_df: pd.DataFrame) -> None:
        assert (beh_df["avg_amount_7d"] > 0).all()

    def test_unique_merchants_at_least_one(self, beh_df: pd.DataFrame) -> None:
        assert (beh_df["unique_merchants_24h"] >= 1).all()

    def test_amount_deviation_finite(self, beh_df: pd.DataFrame) -> None:
        assert beh_df["amount_deviation"].isna().sum() == 0


class TestNetworkFeatures:
    """Test network/device/geo features."""

    @pytest.fixture()
    def net_df(self, sample_transactions: list[Transaction]) -> pd.DataFrame:
        df = compute_transaction_features(preprocess(sample_transactions))
        df = compute_behavioral_features(df)
        return compute_network_features(df)

    def test_shared_device_at_least_one(self, net_df: pd.DataFrame) -> None:
        assert (net_df["shared_device_count"] >= 1).all()

    def test_unique_ips_at_least_one(self, net_df: pd.DataFrame) -> None:
        assert (net_df["unique_ips_24h"] >= 1).all()

    def test_geo_distance_non_negative(self, net_df: pd.DataFrame) -> None:
        assert (net_df["geo_distance_from_home"] >= 0).all()


class TestFeaturePipeline:
    """Test end-to-end feature pipeline."""

    def test_all_features_present(self, sample_transactions: list[Transaction]) -> None:
        pipeline = FeaturePipeline()
        df = pipeline.run(sample_transactions)
        for col in pipeline.feature_columns:
            assert col in df.columns, f"Missing: {col}"

    def test_no_nans_in_features(self, sample_transactions: list[Transaction]) -> None:
        pipeline = FeaturePipeline()
        df = pipeline.run(sample_transactions)
        for col in pipeline.feature_columns:
            assert not df[col].isna().any(), f"NaN in {col}"

    def test_preserves_labels(self, sample_transactions: list[Transaction]) -> None:
        pipeline = FeaturePipeline()
        df = pipeline.run(sample_transactions)
        assert "is_fraud" in df.columns

    def test_correct_row_count(self, sample_transactions: list[Transaction]) -> None:
        pipeline = FeaturePipeline()
        df = pipeline.run(sample_transactions)
        assert len(df) == len(sample_transactions)

    def test_feature_column_count(self) -> None:
        pipeline = FeaturePipeline()
        assert len(pipeline.feature_columns) == 20
