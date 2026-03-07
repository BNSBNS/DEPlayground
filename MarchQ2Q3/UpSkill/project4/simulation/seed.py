"""Seed reference data: 100 products, 500 customers, 3 warehouses, 6 regions into Redis."""
from __future__ import annotations

import asyncio
import json
import uuid

import redis.asyncio as aioredis

from src.config import settings
from src.logging import get_logger, setup_logging

log = get_logger(__name__)

CATEGORIES = ["Electronics", "Clothing", "Home & Garden", "Sports", "Food & Beverage"]
SUBCATEGORIES: dict[str, list[str]] = {
    "Electronics": ["Phones", "Laptops", "Tablets", "Audio", "Cameras"],
    "Clothing": ["Shirts", "Pants", "Shoes", "Accessories", "Outerwear"],
    "Home & Garden": ["Furniture", "Kitchen", "Decor", "Lighting", "Tools"],
    "Sports": ["Running", "Cycling", "Swimming", "Team Sports", "Fitness"],
    "Food & Beverage": ["Snacks", "Beverages", "Organic", "Frozen", "Bakery"],
}
TIERS = ["bronze", "silver", "gold", "platinum"]
REGIONS = ["us-east", "us-west", "eu-west", "eu-central", "ap-southeast", "ap-northeast"]
WAREHOUSES = ["warehouse-us", "warehouse-eu", "warehouse-ap"]


def _generate_products(count: int = 100) -> list[dict[str, str | float | bool]]:
    """Generate product reference data."""
    import random

    products = []
    for i in range(count):
        cat = CATEGORIES[i % len(CATEGORIES)]
        subcats = SUBCATEGORIES[cat]
        products.append({
            "product_id": f"prod-{i:04d}",
            "name": f"{cat} Item {i}",
            "category": cat,
            "subcategory": subcats[i % len(subcats)],
            "base_price": round(random.uniform(5.0, 500.0), 2),
            "weight_kg": round(random.uniform(0.1, 25.0), 1),
            "active": True,
        })
    return products


def _generate_customers(count: int = 500) -> list[dict[str, str | float | bool]]:
    """Generate customer reference data."""
    import random

    customers = []
    for i in range(count):
        tier = TIERS[i % len(TIERS)]
        region = REGIONS[i % len(REGIONS)]
        customers.append({
            "customer_id": f"cust-{i:04d}",
            "name": f"Customer {i}",
            "email": f"customer{i}@example.com",
            "tier": tier,
            "region": region,
            "lifetime_value": round(random.uniform(100.0, 50000.0), 2),
            "active": True,
        })
    return customers


def _generate_regions() -> list[dict[str, str]]:
    """Generate region reference data."""
    tz_map = {
        "us-east": "America/New_York",
        "us-west": "America/Los_Angeles",
        "eu-west": "Europe/London",
        "eu-central": "Europe/Berlin",
        "ap-southeast": "Asia/Singapore",
        "ap-northeast": "Asia/Tokyo",
    }
    currency_map = {
        "us-east": "USD",
        "us-west": "USD",
        "eu-west": "GBP",
        "eu-central": "EUR",
        "ap-southeast": "SGD",
        "ap-northeast": "JPY",
    }
    return [
        {
            "region_id": r,
            "name": r.replace("-", " ").title(),
            "timezone": tz_map[r],
            "currency": currency_map[r],
        }
        for r in REGIONS
    ]


async def seed() -> None:
    """Seed all reference data into Redis."""
    setup_logging(json_output=False)
    r = aioredis.from_url(settings.redis.url, decode_responses=False)

    try:
        products = _generate_products()
        customers = _generate_customers()
        regions = _generate_regions()

        pipe = r.pipeline()

        for p in products:
            pipe.set(f"ref:product:{p['product_id']}", json.dumps(p))
        for c in customers:
            pipe.set(f"ref:customer:{c['customer_id']}", json.dumps(c))
        for reg in regions:
            pipe.set(f"ref:region:{reg['region_id']}", json.dumps(reg))
        for w in WAREHOUSES:
            pipe.set(f"ref:warehouse:{w}", json.dumps({"warehouse_id": w}))

        await pipe.execute()

        log.info(
            "seed_completed",
            products=len(products),
            customers=len(customers),
            regions=len(regions),
            warehouses=len(WAREHOUSES),
        )
    finally:
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(seed())
