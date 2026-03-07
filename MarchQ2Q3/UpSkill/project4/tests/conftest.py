from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.events import (
    ClickAction,
    ClickstreamEvent,
    InventoryEvent,
    InventoryReason,
    OrderEvent,
    OrderStatus,
    PaymentEvent,
    PaymentStatus,
)


@pytest.fixture
def sample_order_event() -> OrderEvent:
    return OrderEvent(
        event_id="evt-test-001",
        order_id="ord-test-001",
        customer_id="cust-0001",
        product_id="prod-0010",
        quantity=2,
        unit_price=Decimal("49.99"),
        total_amount=Decimal("99.98"),
        status=OrderStatus.CREATED,
        region="us-east",
        timestamp=datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_click_event() -> ClickstreamEvent:
    return ClickstreamEvent(
        event_id="evt-test-002",
        session_id="sess-test-001",
        customer_id="cust-0001",
        action=ClickAction.PRODUCT_VIEW,
        page_url="/products/prod-0010",
        product_id="prod-0010",
        timestamp=datetime(2026, 2, 26, 10, 0, 5, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_payment_event() -> PaymentEvent:
    return PaymentEvent(
        event_id="evt-test-003",
        payment_id="pay-test-001",
        order_id="ord-test-001",
        customer_id="cust-0001",
        amount=Decimal("99.98"),
        currency="USD",
        status=PaymentStatus.CAPTURED,
        payment_method="credit_card",
        timestamp=datetime(2026, 2, 26, 10, 0, 10, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_inventory_event() -> InventoryEvent:
    return InventoryEvent(
        event_id="evt-test-004",
        product_id="prod-0010",
        warehouse_id="warehouse-us",
        quantity_change=-2,
        reason=InventoryReason.SALE,
        current_stock=148,
        timestamp=datetime(2026, 2, 26, 10, 0, 15, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_failed_payment() -> PaymentEvent:
    return PaymentEvent(
        event_id="evt-test-005",
        payment_id="pay-test-002",
        order_id="ord-test-002",
        customer_id="cust-0050",
        amount=Decimal("199.99"),
        currency="USD",
        status=PaymentStatus.FAILED,
        payment_method="debit_card",
        failure_reason="Insufficient funds",
        timestamp=datetime(2026, 2, 26, 10, 0, 20, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client with common operations."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.hset = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.hincrby = AsyncMock(return_value=1)
    redis.hincrbyfloat = AsyncMock(return_value=1.0)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.sadd = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.rpush = AsyncMock(return_value=1)
    redis.lpop = AsyncMock(return_value=None)
    redis.pipeline = MagicMock()

    # Make pipeline return an async mock with execute
    pipe_mock = AsyncMock()
    pipe_mock.hincrby = MagicMock(return_value=pipe_mock)
    pipe_mock.hincrbyfloat = MagicMock(return_value=pipe_mock)
    pipe_mock.hsetnx = MagicMock(return_value=pipe_mock)
    pipe_mock.expire = MagicMock(return_value=pipe_mock)
    pipe_mock.execute = AsyncMock(return_value=[])
    redis.pipeline.return_value = pipe_mock

    return redis


@pytest.fixture
def mock_kafka_producer() -> AsyncMock:
    """Mock AIOKafkaProducer."""
    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_and_wait = AsyncMock()
    return producer


@pytest.fixture
def sample_customer_data() -> dict[str, Any]:
    return {
        "customer_id": "cust-0001",
        "name": "Customer 1",
        "email": "customer1@example.com",
        "tier": "gold",
        "region": "us-east",
        "lifetime_value": 5000.00,
        "active": True,
    }


@pytest.fixture
def sample_product_data() -> dict[str, Any]:
    return {
        "product_id": "prod-0010",
        "name": "Electronics Item 10",
        "category": "Electronics",
        "subcategory": "Phones",
        "base_price": 49.99,
        "weight_kg": 0.3,
        "active": True,
    }
