from __future__ import annotations

from datetime import datetime

import pytest

from src.models.entities import CUSTOMER, ENTITIES, ORDER, PRODUCT, Entity
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
from src.models.training import TrainingDataset


class TestEntity:
    def test_customer_entity(self) -> None:
        assert CUSTOMER.name == "customer"
        assert CUSTOMER.join_key == "customer_id"

    def test_product_entity(self) -> None:
        assert PRODUCT.name == "product"
        assert PRODUCT.join_key == "product_id"

    def test_order_entity(self) -> None:
        assert ORDER.name == "order"
        assert ORDER.join_key == "order_id"

    def test_entities_lookup(self) -> None:
        assert "customer" in ENTITIES
        assert "product" in ENTITIES
        assert "order" in ENTITIES
        assert ENTITIES["customer"] is CUSTOMER

    def test_custom_entity(self) -> None:
        e = Entity(name="store", join_key="store_id")
        assert e.name == "store"
        assert e.join_key == "store_id"


class TestDataSource:
    def test_batch_source(self) -> None:
        ds = DataSource(
            name="orders",
            source_type="batch",
            table_or_query="public.orders",
        )
        assert ds.source_type == "batch"
        assert ds.table_or_query == "public.orders"
        assert ds.kafka_topic is None

    def test_stream_source(self) -> None:
        ds = DataSource(
            name="order-events",
            source_type="stream",
            kafka_topic="order-events",
        )
        assert ds.source_type == "stream"
        assert ds.kafka_topic == "order-events"
        assert ds.table_or_query is None


class TestFeatureDefinition:
    def test_basic_feature(self, sample_feature: FeatureDefinition) -> None:
        assert sample_feature.name == "total_orders"
        assert sample_feature.entity == "customer"
        assert sample_feature.value_type == ValueType.INT64
        assert sample_feature.status == FeatureStatus.ACTIVE
        assert sample_feature.version == 1

    def test_feature_with_aggregation(self, sample_feature: FeatureDefinition) -> None:
        assert sample_feature.aggregation is not None
        assert sample_feature.aggregation.function == "count"
        assert sample_feature.aggregation.window == "365 days"

    def test_feature_defaults(self) -> None:
        f = FeatureDefinition(
            name="test",
            feature_set="test_set",
            entity="customer",
            value_type=ValueType.FLOAT64,
        )
        assert f.description == ""
        assert f.owner == ""
        assert f.tags == []
        assert f.version == 1
        assert f.status == FeatureStatus.ACTIVE
        assert f.freshness_sla_minutes == 60

    def test_value_types(self) -> None:
        assert ValueType.INT64.value == "int64"
        assert ValueType.FLOAT64.value == "float64"
        assert ValueType.STRING.value == "string"
        assert ValueType.BOOL.value == "bool"
        assert ValueType.TIMESTAMP.value == "timestamp"
        assert ValueType.JSON.value == "json"

    def test_feature_status(self) -> None:
        assert FeatureStatus.ACTIVE.value == "active"
        assert FeatureStatus.DEPRECATED.value == "deprecated"
        assert FeatureStatus.EXPERIMENTAL.value == "experimental"


class TestFeatureSet:
    def test_basic_set(self, sample_feature_set: FeatureSet) -> None:
        assert sample_feature_set.name == "customer_order_features"
        assert sample_feature_set.entity == "customer"
        assert len(sample_feature_set.features) == 3
        assert sample_feature_set.schedule == "daily"

    def test_defaults(self) -> None:
        fs = FeatureSet(name="test", entity="customer")
        assert fs.features == []
        assert fs.schedule == "daily"
        assert fs.batch_source is None


class TestFeatureValue:
    def test_feature_value(self, sample_feature_value: FeatureValue) -> None:
        assert sample_feature_value.entity_key == "CUST-0001"
        assert sample_feature_value.feature_name == "total_orders"
        assert sample_feature_value.value == 42

    def test_none_value(self) -> None:
        fv = FeatureValue(
            entity_key="X",
            feature_name="f",
            value=None,
            event_timestamp=datetime.utcnow(),
        )
        assert fv.value is None


class TestTrainingDataset:
    def test_training_dataset(self) -> None:
        ds = TrainingDataset(
            id="abc-123",
            name="churn_v1",
            entity_type="customer",
            features=["total_orders", "total_spend"],
            row_count=1000,
        )
        assert ds.id == "abc-123"
        assert ds.row_count == 1000
        assert len(ds.features) == 2


class TestFeatureStats:
    def test_stats(self, sample_stats: FeatureStats) -> None:
        assert sample_stats.feature_name == "total_orders"
        assert sample_stats.count == 1000
        assert sample_stats.null_pct == 0.05
        assert sample_stats.mean == 25.5

    def test_stats_defaults(self) -> None:
        s = FeatureStats(
            feature_name="test",
            window_start=datetime.utcnow(),
            window_end=datetime.utcnow(),
        )
        assert s.count == 0
        assert s.null_count == 0
        assert s.mean is None
        assert s.value_distribution == {}
