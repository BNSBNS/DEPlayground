from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderStatus(str, enum.Enum):
    CREATED = "created"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class ClickAction(str, enum.Enum):
    PAGE_VIEW = "page_view"
    PRODUCT_VIEW = "product_view"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    SEARCH = "search"
    CHECKOUT_START = "checkout_start"
    CHECKOUT_COMPLETE = "checkout_complete"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    CHARGEBACK = "chargeback"


class InventoryReason(str, enum.Enum):
    SALE = "sale"
    RESTOCK = "restock"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    DAMAGED = "damaged"
    TRANSFER = "transfer"


class OrderEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    customer_id: str
    product_id: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, decimal_places=2)
    total_amount: Decimal = Field(ge=0, decimal_places=2)
    status: OrderStatus
    region: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def kafka_key(self) -> str:
        return self.order_id


class ClickstreamEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    customer_id: str
    action: ClickAction
    page_url: str = ""
    product_id: str | None = None
    search_query: str | None = None
    referrer: str = ""
    user_agent: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def kafka_key(self) -> str:
        return self.session_id


class PaymentEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payment_id: str
    order_id: str
    customer_id: str
    amount: Decimal = Field(ge=0, decimal_places=2)
    currency: str = "USD"
    status: PaymentStatus
    payment_method: str = "credit_card"
    failure_reason: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def kafka_key(self) -> str:
        return self.payment_id


class InventoryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    warehouse_id: str
    quantity_change: int
    reason: InventoryReason
    current_stock: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def kafka_key(self) -> str:
        return self.product_id
