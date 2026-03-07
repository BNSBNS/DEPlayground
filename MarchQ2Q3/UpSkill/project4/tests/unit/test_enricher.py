from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.processors.enricher import Enricher


@pytest.fixture
def enricher(mock_redis: AsyncMock) -> Enricher:
    return Enricher(mock_redis)


class TestEnricher:
    async def test_get_customer_found(
        self,
        enricher: Enricher,
        mock_redis: AsyncMock,
        sample_customer_data: dict[str, Any],
    ) -> None:
        mock_redis.get.return_value = json.dumps(sample_customer_data).encode()
        result = await enricher.get_customer("cust-0001")
        assert result is not None
        assert result["customer_id"] == "cust-0001"
        assert result["tier"] == "gold"
        mock_redis.get.assert_called_once_with("ref:customer:cust-0001")

    async def test_get_customer_not_found(
        self, enricher: Enricher, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        result = await enricher.get_customer("cust-9999")
        assert result is None

    async def test_get_product_found(
        self,
        enricher: Enricher,
        mock_redis: AsyncMock,
        sample_product_data: dict[str, Any],
    ) -> None:
        mock_redis.get.return_value = json.dumps(sample_product_data).encode()
        result = await enricher.get_product("prod-0010")
        assert result is not None
        assert result["category"] == "Electronics"

    async def test_get_product_not_found(
        self, enricher: Enricher, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        result = await enricher.get_product("prod-9999")
        assert result is None

    async def test_enrich_order_with_data(
        self,
        enricher: Enricher,
        mock_redis: AsyncMock,
        sample_customer_data: dict[str, Any],
        sample_product_data: dict[str, Any],
    ) -> None:
        # First call returns customer, second returns product
        mock_redis.get.side_effect = [
            json.dumps(sample_customer_data).encode(),
            json.dumps(sample_product_data).encode(),
        ]

        payload = {
            "order_id": "ord-001",
            "customer_id": "cust-0001",
            "product_id": "prod-0010",
            "total_amount": "99.98",
        }

        enriched = await enricher.enrich_order(payload)
        assert enriched["customer_name"] == "Customer 1"
        assert enriched["customer_tier"] == "gold"
        assert enriched["customer_region"] == "us-east"
        assert enriched["product_name"] == "Electronics Item 10"
        assert enriched["product_category"] == "Electronics"
        # Original fields preserved
        assert enriched["order_id"] == "ord-001"

    async def test_enrich_order_no_reference_data(
        self, enricher: Enricher, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        payload = {
            "order_id": "ord-002",
            "customer_id": "cust-9999",
            "product_id": "prod-9999",
        }
        enriched = await enricher.enrich_order(payload)
        assert "customer_name" not in enriched
        assert "product_name" not in enriched
        assert enriched["order_id"] == "ord-002"
