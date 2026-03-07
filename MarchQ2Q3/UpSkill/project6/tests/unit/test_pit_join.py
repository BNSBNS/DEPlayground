from __future__ import annotations

from datetime import datetime

import pytest

from src.serving.pit_join import build_pit_join_query, build_single_feature_pit_query


class TestBuildPITJoinQuery:
    def test_single_feature(self) -> None:
        query = build_pit_join_query(
            feature_names=["total_orders"],
            entity_join_key="customer_id",
            start_time=datetime(2025, 1, 1),
            end_time=datetime(2025, 1, 31),
        )

        assert "total_orders_latest" in query
        assert "DISTINCT ON" in query
        assert "feature_values" in query
        assert "customer_id" in query
        assert "2025-01-01" in query
        assert "2025-01-31" in query

    def test_multiple_features(self) -> None:
        query = build_pit_join_query(
            feature_names=["total_orders", "total_spend", "avg_order_value"],
            entity_join_key="customer_id",
            start_time=datetime(2025, 1, 1),
            end_time=datetime(2025, 6, 30),
        )

        assert "total_orders_latest" in query
        assert "total_spend_latest" in query
        assert "avg_order_value_latest" in query
        assert query.count("LEFT JOIN") == 3  # entity_df joins
        assert query.count("DISTINCT ON") == 3

    def test_pit_ordering(self) -> None:
        query = build_pit_join_query(
            feature_names=["total_orders"],
            entity_join_key="customer_id",
            start_time=datetime(2025, 1, 1),
            end_time=datetime(2025, 1, 31),
        )

        # Must order by event_timestamp DESC for PIT correctness
        assert "event_timestamp DESC" in query

    def test_event_timestamp_filter(self) -> None:
        query = build_pit_join_query(
            feature_names=["total_orders"],
            entity_join_key="customer_id",
            start_time=datetime(2025, 1, 1),
            end_time=datetime(2025, 1, 31),
        )

        # PIT: feature timestamp must be <= entity timestamp
        assert "fv.event_timestamp <= e.event_timestamp" in query

    def test_custom_entity_table(self) -> None:
        query = build_pit_join_query(
            feature_names=["total_orders"],
            entity_join_key="customer_id",
            start_time=datetime(2025, 1, 1),
            end_time=datetime(2025, 1, 31),
            entity_table="my_entities",
        )

        assert "my_entities" in query

    def test_different_entity_key(self) -> None:
        query = build_pit_join_query(
            feature_names=["units_sold"],
            entity_join_key="product_id",
            start_time=datetime(2025, 1, 1),
            end_time=datetime(2025, 12, 31),
        )

        assert "product_id" in query


class TestBuildSingleFeaturePITQuery:
    def test_basic_query(self) -> None:
        query = build_single_feature_pit_query(
            feature_name="total_orders",
            entity_key="CUST-0001",
            as_of=datetime(2025, 6, 15, 12, 0),
        )

        assert "total_orders" in query
        assert "CUST-0001" in query
        assert "DISTINCT ON" in query
        assert "event_timestamp DESC" in query
        assert "LIMIT 1" in query

    def test_pit_constraint(self) -> None:
        as_of = datetime(2025, 6, 15)
        query = build_single_feature_pit_query(
            feature_name="total_spend",
            entity_key="CUST-0002",
            as_of=as_of,
        )

        assert f"event_timestamp <= '{as_of.isoformat()}'" in query
