from __future__ import annotations

import enum
from decimal import Decimal

from pydantic import BaseModel, Field


class CustomerTier(str, enum.Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class Product(BaseModel):
    product_id: str
    name: str
    category: str
    subcategory: str = ""
    base_price: Decimal = Field(ge=0, decimal_places=2)
    weight_kg: float = 0.0
    active: bool = True


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    tier: CustomerTier
    region: str
    lifetime_value: Decimal = Decimal("0.00")
    active: bool = True


class Region(BaseModel):
    region_id: str
    name: str
    timezone: str
    currency: str = "USD"
