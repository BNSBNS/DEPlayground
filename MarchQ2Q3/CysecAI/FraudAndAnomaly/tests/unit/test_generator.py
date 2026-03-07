"""Tests for synthetic transaction generator.

Validates data quality, schema correctness, fraud distribution,
and pattern characteristics per Phase 1 spec.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.config import GeneratorSettings
from src.data.generator import (
    MERCHANT_CATEGORIES,
    ROUND_FRAUD_AMOUNTS,
    FraudStrategy,
    Transaction,
    TransactionGenerator,
)


class TestTransactionModel:
    """Transaction Pydantic model tests."""

    def test_create_valid_transaction(self) -> None:
        tx = Transaction(
            user_id="user-00001",
            amount=Decimal("99.99"),
            merchant_category="grocery",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            device_id="device-abc",
            ip_address="10.0.0.1",
            geo_lat=40.7128,
            geo_lon=-74.0060,
        )
        assert tx.user_id == "user-00001"
        assert tx.amount == Decimal("99.99")
        assert tx.is_fraud is False
        assert tx.fraud_strategy is None

    def test_auto_generates_uuid(self) -> None:
        tx = Transaction(
            user_id="u",
            amount=Decimal("1.00"),
            merchant_category="grocery",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            device_id="d",
            ip_address="10.0.0.1",
            geo_lat=0.0,
            geo_lon=0.0,
        )
        uuid.UUID(tx.transaction_id)  # Validates UUID format

    def test_amount_must_be_positive(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            Transaction(
                user_id="u",
                amount=Decimal("0.00"),
                merchant_category="grocery",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                device_id="d",
                ip_address="10.0.0.1",
                geo_lat=0.0,
                geo_lon=0.0,
            )


class TestGeneratorDataset:
    """Tests for the generated dataset as a whole."""

    def test_correct_count(self, sample_transactions: list[Transaction]) -> None:
        assert len(sample_transactions) == 1000

    def test_fraud_rate_within_tolerance(self, sample_transactions: list[Transaction]) -> None:
        fraud_count = sum(1 for tx in sample_transactions if tx.is_fraud)
        fraud_rate = fraud_count / len(sample_transactions)
        # 3% target, allow 1-5% tolerance for small datasets
        assert 0.01 <= fraud_rate <= 0.05, f"Fraud rate {fraud_rate:.3f} out of range"

    def test_all_fields_non_null(self, sample_transactions: list[Transaction]) -> None:
        for tx in sample_transactions:
            assert tx.transaction_id
            assert tx.user_id
            assert tx.amount > 0
            assert tx.merchant_category
            assert tx.timestamp is not None
            assert tx.device_id
            assert tx.ip_address

    def test_amounts_are_decimal(self, sample_transactions: list[Transaction]) -> None:
        for tx in sample_transactions:
            assert isinstance(tx.amount, Decimal), f"Amount {tx.amount} is not Decimal"

    def test_sorted_by_timestamp(self, sample_transactions: list[Transaction]) -> None:
        timestamps = [tx.timestamp for tx in sample_transactions]
        assert timestamps == sorted(timestamps)

    def test_merchant_categories_valid(self, sample_transactions: list[Transaction]) -> None:
        for tx in sample_transactions:
            assert tx.merchant_category in MERCHANT_CATEGORIES

    def test_geo_coordinates_valid(self, sample_transactions: list[Transaction]) -> None:
        for tx in sample_transactions:
            assert -90.0 <= tx.geo_lat <= 90.0
            assert -180.0 <= tx.geo_lon <= 180.0

    def test_timestamps_span_30_days(self, sample_transactions: list[Transaction]) -> None:
        earliest = min(tx.timestamp for tx in sample_transactions)
        latest = max(tx.timestamp for tx in sample_transactions)
        span_days = (latest - earliest).days
        assert 25 <= span_days <= 35, f"Timestamp span {span_days} days"

    def test_multiple_users_present(self, sample_transactions: list[Transaction]) -> None:
        unique_users = {tx.user_id for tx in sample_transactions}
        assert len(unique_users) > 10


class TestDeterminism:
    """Verify deterministic generation with same seed."""

    def test_same_seed_same_output(self) -> None:
        settings = GeneratorSettings(num_transactions=1000, seed=42, num_users=100)
        gen1 = TransactionGenerator(settings)
        gen2 = TransactionGenerator(settings)
        txs1 = gen1.generate()
        txs2 = gen2.generate()

        assert len(txs1) == len(txs2)
        for a, b in zip(txs1, txs2, strict=True):
            # transaction_id uses uuid4() (non-deterministic), so compare data fields
            assert a.user_id == b.user_id
            assert a.amount == b.amount
            assert a.is_fraud == b.is_fraud
            assert a.merchant_category == b.merchant_category
            assert a.timestamp == b.timestamp

    def test_different_seed_different_output(self) -> None:
        s1 = GeneratorSettings(num_transactions=1000, seed=42, num_users=100)
        s2 = GeneratorSettings(num_transactions=1000, seed=99, num_users=100)
        txs1 = TransactionGenerator(s1).generate()
        txs2 = TransactionGenerator(s2).generate()

        # At least some transactions should differ in amount
        diffs = sum(1 for a, b in zip(txs1, txs2, strict=True) if a.amount != b.amount)
        assert diffs > 100


class TestFraudPatterns:
    """Verify fraud transactions exhibit expected anomaly characteristics."""

    def test_all_strategies_present(self, sample_transactions: list[Transaction]) -> None:
        fraud_txs = [tx for tx in sample_transactions if tx.is_fraud]
        strategies = {tx.fraud_strategy for tx in fraud_txs}
        for strategy in FraudStrategy:
            assert strategy.value in strategies, f"Missing strategy: {strategy}"

    def test_amount_spike_is_high(self, sample_transactions: list[Transaction]) -> None:
        spikes = [
            tx for tx in sample_transactions if tx.fraud_strategy == FraudStrategy.AMOUNT_SPIKE
        ]
        assert len(spikes) > 0
        # All spike amounts should be >= $75 (5x minimum avg of $15)
        for tx in spikes:
            assert tx.amount >= Decimal("75.00"), f"Spike amount {tx.amount} too low"

    def test_new_device_location_far_from_home(
        self, sample_transactions: list[Transaction], generator: TransactionGenerator
    ) -> None:
        new_device_txs = [
            tx
            for tx in sample_transactions
            if tx.fraud_strategy == FraudStrategy.NEW_DEVICE_LOCATION
        ]
        assert len(new_device_txs) > 0

        # Find the user profile and verify distance
        user_map = {u.user_id: u for u in generator._users}
        for tx in new_device_txs:
            user = user_map[tx.user_id]
            dist = TransactionGenerator.haversine_km(
                user.home_lat, user.home_lon, tx.geo_lat, tx.geo_lon
            )
            assert dist > 300, f"Distance {dist:.0f}km too close"

    def test_round_amounts_match_expected(self, sample_transactions: list[Transaction]) -> None:
        round_txs = [
            tx for tx in sample_transactions if tx.fraud_strategy == FraudStrategy.ROUND_AMOUNT
        ]
        assert len(round_txs) > 0
        for tx in round_txs:
            assert tx.amount in ROUND_FRAUD_AMOUNTS

    def test_category_mismatch_at_unusual_hours(
        self, sample_transactions: list[Transaction]
    ) -> None:
        mismatch_txs = [
            tx for tx in sample_transactions if tx.fraud_strategy == FraudStrategy.CATEGORY_MISMATCH
        ]
        assert len(mismatch_txs) > 0
        for tx in mismatch_txs:
            assert 2 <= tx.timestamp.hour <= 4, f"Hour {tx.timestamp.hour} not unusual"

    def test_fraud_strategies_roughly_balanced(
        self, sample_transactions: list[Transaction]
    ) -> None:
        fraud_txs = [tx for tx in sample_transactions if tx.is_fraud]
        counts = Counter(tx.fraud_strategy for tx in fraud_txs)
        # With 30 fraud tx / 5 strategies = ~6 each. Allow 2-15 range.
        for strategy, count in counts.items():
            assert 2 <= count <= 15, f"Strategy {strategy} has {count}"


class TestHaversine:
    """Test haversine distance calculation."""

    def test_same_point_zero_distance(self) -> None:
        dist = TransactionGenerator.haversine_km(40.0, -74.0, 40.0, -74.0)
        assert dist < 0.01

    def test_known_distance(self) -> None:
        # NYC to LA: ~3944 km
        dist = TransactionGenerator.haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < dist < 4000
