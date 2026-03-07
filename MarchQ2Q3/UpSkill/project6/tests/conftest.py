from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.entities import CUSTOMER, PRODUCT, Entity
from src.models.features import (
    AggSpec,
    FeatureDefinition,
    FeatureSet,
    FeatureStatus,
    FeatureValue,
    ValueType,
)
from src.models.sources import DataSource
from src.models.stats import FeatureStats


@pytest.fixture
def sample_entity() -> Entity:
    return CUSTOMER


@pytest.fixture
def sample_feature() -> FeatureDefinition:
    return FeatureDefinition(
        name="total_orders",
        feature_set="customer_order_features",
        entity="customer",
        value_type=ValueType.INT64,
        description="Total number of orders",
        owner="data-team",
        tags=["orders"],
        batch_source="orders",
        stream_source="order-events",
        aggregation=AggSpec(function="count", window="365 days"),
        freshness_sla_minutes=120,
    )


@pytest.fixture
def sample_feature_no_agg() -> FeatureDefinition:
    return FeatureDefinition(
        name="days_since_last_order",
        feature_set="customer_order_features",
        entity="customer",
        value_type=ValueType.INT64,
        description="Days since last order",
        transform="EXTRACT(DAY FROM NOW() - MAX(event_timestamp))",
    )


@pytest.fixture
def sample_feature_set() -> FeatureSet:
    return FeatureSet(
        name="customer_order_features",
        entity="customer",
        features=["total_orders", "total_spend", "avg_order_value"],
        batch_source="orders",
        stream_source="order-events",
        schedule="daily",
    )


@pytest.fixture
def sample_features() -> list[FeatureDefinition]:
    return [
        FeatureDefinition(
            name="total_orders",
            feature_set="customer_order_features",
            entity="customer",
            value_type=ValueType.INT64,
            aggregation=AggSpec(function="count", window="365 days"),
        ),
        FeatureDefinition(
            name="total_spend",
            feature_set="customer_order_features",
            entity="customer",
            value_type=ValueType.FLOAT64,
            aggregation=AggSpec(function="sum", window="365 days"),
        ),
        FeatureDefinition(
            name="avg_order_value",
            feature_set="customer_order_features",
            entity="customer",
            value_type=ValueType.FLOAT64,
            aggregation=AggSpec(function="avg", window="365 days"),
        ),
    ]


@pytest.fixture
def sample_feature_value() -> FeatureValue:
    return FeatureValue(
        entity_key="CUST-0001",
        feature_name="total_orders",
        value=42,
        event_timestamp=datetime(2025, 1, 15, 12, 0, 0),
    )


@pytest.fixture
def sample_data_source() -> DataSource:
    return DataSource(
        name="orders",
        source_type="batch",
        table_or_query="public.orders",
    )


@pytest.fixture
def sample_stats() -> FeatureStats:
    return FeatureStats(
        feature_name="total_orders",
        window_start=datetime(2025, 1, 1),
        window_end=datetime(2025, 1, 31),
        count=1000,
        null_count=50,
        null_pct=0.05,
        mean=25.5,
        stddev=10.2,
        min=0.0,
        max=100.0,
        p25=15.0,
        p50=25.0,
        p75=35.0,
        p95=55.0,
        unique_count=80,
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.mget = AsyncMock(return_value=[])
    redis.setex = AsyncMock()
    redis.pipeline = MagicMock()
    pipe = AsyncMock()
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline.return_value = pipe
    return redis


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool
