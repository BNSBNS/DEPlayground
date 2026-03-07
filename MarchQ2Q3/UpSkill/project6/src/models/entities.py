from __future__ import annotations

from pydantic import BaseModel


class Entity(BaseModel):
    name: str
    join_key: str


CUSTOMER = Entity(name="customer", join_key="customer_id")
PRODUCT = Entity(name="product", join_key="product_id")
ORDER = Entity(name="order", join_key="order_id")

ENTITIES: dict[str, Entity] = {
    e.name: e for e in [CUSTOMER, PRODUCT, ORDER]
}
