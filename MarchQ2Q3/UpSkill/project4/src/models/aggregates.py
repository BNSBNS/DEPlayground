from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RealTimeSales(BaseModel):
    window_start: datetime
    window_end: datetime
    region: str
    total_orders: int = 0
    total_revenue: Decimal = Decimal("0.00")
    avg_order_value: Decimal = Decimal("0.00")
    cancelled_orders: int = 0
    unique_customers: int = 0
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerActivity(BaseModel):
    customer_id: str
    window_start: datetime
    window_end: datetime
    page_views: int = 0
    product_views: int = 0
    cart_additions: int = 0
    searches: int = 0
    orders_placed: int = 0
    total_spent: Decimal = Decimal("0.00")
    session_count: int = 0
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProductPerformance(BaseModel):
    product_id: str
    window_start: datetime
    window_end: datetime
    views: int = 0
    cart_additions: int = 0
    orders: int = 0
    revenue: Decimal = Decimal("0.00")
    returns: int = 0
    conversion_rate: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AnomalySeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyFlag(BaseModel):
    anomaly_id: str
    rule_name: str
    severity: AnomalySeverity
    entity_type: str
    entity_id: str
    metric_name: str
    metric_value: float
    threshold: float
    description: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
