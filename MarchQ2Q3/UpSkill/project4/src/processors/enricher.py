from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from src.logging import get_logger

log = get_logger(__name__)


class Enricher:
    """Enriches events with customer/product reference data from Redis."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """Look up customer reference data."""
        raw = await self._redis.get(f"ref:customer:{customer_id}")
        if raw is None:
            log.debug("customer_not_found", customer_id=customer_id)
            return None
        return json.loads(raw.decode() if isinstance(raw, bytes) else raw)

    async def get_product(self, product_id: str) -> dict[str, Any] | None:
        """Look up product reference data."""
        raw = await self._redis.get(f"ref:product:{product_id}")
        if raw is None:
            log.debug("product_not_found", product_id=product_id)
            return None
        return json.loads(raw.decode() if isinstance(raw, bytes) else raw)

    async def enrich_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Enrich an order event with customer and product data."""
        customer = await self.get_customer(payload.get("customer_id", ""))
        product = await self.get_product(payload.get("product_id", ""))

        enriched = {**payload}
        if customer:
            enriched["customer_name"] = customer.get("name", "")
            enriched["customer_tier"] = customer.get("tier", "")
            enriched["customer_region"] = customer.get("region", "")
        if product:
            enriched["product_name"] = product.get("name", "")
            enriched["product_category"] = product.get("category", "")

        return enriched
