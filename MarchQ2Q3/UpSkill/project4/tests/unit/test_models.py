from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.aggregates import AnomalyFlag, AnomalySeverity, RealTimeSales
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
from src.models.reference import Customer, CustomerTier, Product, Region


class TestOrderEvent:
    def test_valid_order(self, sample_order_event: OrderEvent) -> None:
        assert sample_order_event.order_id == "ord-test-001"
        assert sample_order_event.quantity == 2
        assert sample_order_event.total_amount == Decimal("99.98")
        assert sample_order_event.status == OrderStatus.CREATED

    def test_kafka_key(self, sample_order_event: OrderEvent) -> None:
        assert sample_order_event.kafka_key == "ord-test-001"

    def test_invalid_quantity(self) -> None:
        with pytest.raises(ValidationError):
            OrderEvent(
                order_id="ord-bad",
                customer_id="cust-0001",
                product_id="prod-0001",
                quantity=0,
                unit_price=Decimal("10.00"),
                total_amount=Decimal("0.00"),
                status=OrderStatus.CREATED,
                region="us-east",
            )

    def test_negative_price_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrderEvent(
                order_id="ord-bad",
                customer_id="cust-0001",
                product_id="prod-0001",
                quantity=1,
                unit_price=Decimal("-5.00"),
                total_amount=Decimal("-5.00"),
                status=OrderStatus.CREATED,
                region="us-east",
            )

    def test_all_order_statuses(self) -> None:
        for status in OrderStatus:
            event = OrderEvent(
                order_id="ord-status",
                customer_id="cust-0001",
                product_id="prod-0001",
                quantity=1,
                unit_price=Decimal("10.00"),
                total_amount=Decimal("10.00"),
                status=status,
                region="us-east",
            )
            assert event.status == status

    def test_serialization_roundtrip(self, sample_order_event: OrderEvent) -> None:
        data = sample_order_event.model_dump(mode="json")
        restored = OrderEvent.model_validate(data)
        assert restored.order_id == sample_order_event.order_id
        assert restored.total_amount == sample_order_event.total_amount


class TestClickstreamEvent:
    def test_valid_click(self, sample_click_event: ClickstreamEvent) -> None:
        assert sample_click_event.action == ClickAction.PRODUCT_VIEW
        assert sample_click_event.product_id == "prod-0010"

    def test_kafka_key(self, sample_click_event: ClickstreamEvent) -> None:
        assert sample_click_event.kafka_key == "sess-test-001"

    def test_optional_product_id(self) -> None:
        event = ClickstreamEvent(
            session_id="sess-001",
            customer_id="cust-001",
            action=ClickAction.SEARCH,
            search_query="test query",
        )
        assert event.product_id is None
        assert event.search_query == "test query"

    def test_all_click_actions(self) -> None:
        for action in ClickAction:
            event = ClickstreamEvent(
                session_id="sess-001",
                customer_id="cust-001",
                action=action,
            )
            assert event.action == action


class TestPaymentEvent:
    def test_valid_payment(self, sample_payment_event: PaymentEvent) -> None:
        assert sample_payment_event.status == PaymentStatus.CAPTURED
        assert sample_payment_event.amount == Decimal("99.98")

    def test_failed_payment(self, sample_failed_payment: PaymentEvent) -> None:
        assert sample_failed_payment.status == PaymentStatus.FAILED
        assert sample_failed_payment.failure_reason == "Insufficient funds"

    def test_kafka_key(self, sample_payment_event: PaymentEvent) -> None:
        assert sample_payment_event.kafka_key == "pay-test-001"


class TestInventoryEvent:
    def test_valid_inventory(self, sample_inventory_event: InventoryEvent) -> None:
        assert sample_inventory_event.quantity_change == -2
        assert sample_inventory_event.reason == InventoryReason.SALE

    def test_kafka_key(self, sample_inventory_event: InventoryEvent) -> None:
        assert sample_inventory_event.kafka_key == "prod-0010"

    def test_negative_stock_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InventoryEvent(
                product_id="prod-001",
                warehouse_id="wh-001",
                quantity_change=-5,
                reason=InventoryReason.SALE,
                current_stock=-1,
            )


class TestAggregateModels:
    def test_realtime_sales_defaults(self) -> None:
        now = datetime.now(tz=timezone.utc)
        sales = RealTimeSales(
            window_start=now,
            window_end=now,
            region="us-east",
        )
        assert sales.total_orders == 0
        assert sales.total_revenue == Decimal("0.00")

    def test_anomaly_flag(self) -> None:
        anomaly = AnomalyFlag(
            anomaly_id="anom-001",
            rule_name="high_value_order",
            severity=AnomalySeverity.HIGH,
            entity_type="order",
            entity_id="ord-001",
            metric_name="order_amount",
            metric_value=1500.0,
            threshold=500.0,
            description="Order exceeds threshold",
        )
        assert anomaly.resolved is False
        assert anomaly.severity == AnomalySeverity.HIGH


class TestReferenceModels:
    def test_product(self) -> None:
        product = Product(
            product_id="prod-001",
            name="Test Product",
            category="Electronics",
            base_price=Decimal("29.99"),
        )
        assert product.active is True

    def test_customer(self) -> None:
        customer = Customer(
            customer_id="cust-001",
            name="Test Customer",
            email="test@example.com",
            tier=CustomerTier.GOLD,
            region="us-east",
        )
        assert customer.tier == CustomerTier.GOLD

    def test_region(self) -> None:
        region = Region(
            region_id="us-east",
            name="US East",
            timezone="America/New_York",
        )
        assert region.currency == "USD"
