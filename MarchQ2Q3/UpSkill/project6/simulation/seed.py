"""Seed the feature store with synthetic data.

Generates:
- 5,000 customers
- 50,000 orders
- 200 products
- 100,000 clickstream events
- 90 days of historical feature values
"""
from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta

import asyncpg
import structlog
from redis.asyncio import Redis

from src.config import get_settings

logger = structlog.get_logger(__name__)

NUM_CUSTOMERS = 5_000
NUM_ORDERS = 50_000
NUM_PRODUCTS = 200
NUM_CLICKSTREAM = 100_000
HISTORY_DAYS = 90


def _random_ts(days_back: int = HISTORY_DAYS) -> datetime:
    return datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


async def seed_customers(conn: asyncpg.Connection) -> list[str]:
    customer_ids = [str(uuid.uuid4())[:12] for _ in range(NUM_CUSTOMERS)]
    logger.info("seeding_customers", count=NUM_CUSTOMERS)

    for cid in customer_ids:
        ts = _random_ts()
        features = {
            "total_orders": random.randint(0, 100),
            "total_spend": round(random.uniform(0, 5000), 2),
            "avg_order_value": round(random.uniform(10, 200), 2),
            "days_since_last_order": random.randint(0, 90),
            "order_count_7d": random.randint(0, 10),
            "page_views_7d": random.randint(0, 200),
            "cart_additions_7d": random.randint(0, 20),
            "search_count_7d": random.randint(0, 50),
            "session_count_30d": random.randint(0, 60),
        }
        for fname, val in features.items():
            await conn.execute(
                """
                INSERT INTO feature_values (entity_key, feature_name, value, event_timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                cid, fname, json.dumps(val), ts,
            )

    return customer_ids


async def seed_products(conn: asyncpg.Connection) -> list[str]:
    product_ids = [f"PROD-{i:04d}" for i in range(NUM_PRODUCTS)]
    logger.info("seeding_products", count=NUM_PRODUCTS)

    for pid in product_ids:
        ts = _random_ts()
        features = {
            "total_sales": round(random.uniform(0, 50000), 2),
            "units_sold": random.randint(0, 1000),
            "avg_rating": round(random.uniform(1.0, 5.0), 1),
            "view_count_30d": random.randint(0, 5000),
            "conversion_rate": round(random.uniform(0.01, 0.15), 4),
        }
        for fname, val in features.items():
            await conn.execute(
                """
                INSERT INTO feature_values (entity_key, feature_name, value, event_timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                pid, fname, json.dumps(val), ts,
            )

    return product_ids


async def seed_orders(
    conn: asyncpg.Connection,
    customer_ids: list[str],
    product_ids: list[str],
) -> list[str]:
    order_ids = [f"ORD-{i:06d}" for i in range(NUM_ORDERS)]
    logger.info("seeding_orders", count=NUM_ORDERS)

    for oid in order_ids:
        ts = _random_ts()
        features = {
            "item_count": random.randint(1, 10),
            "total_amount": round(random.uniform(10, 500), 2),
            "payment_method_mode": random.choice(["credit_card", "debit_card", "paypal"]),
            "delivery_time_avg": round(random.uniform(12, 120), 1),
            "return_rate": round(random.uniform(0, 0.3), 3),
        }
        for fname, val in features.items():
            await conn.execute(
                """
                INSERT INTO feature_values (entity_key, feature_name, value, event_timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                oid, fname, json.dumps(val), ts,
            )

    return order_ids


async def seed_historical_values(
    conn: asyncpg.Connection,
    customer_ids: list[str],
) -> None:
    """Seed 90 days of daily snapshots for key features."""
    logger.info("seeding_historical_values", days=HISTORY_DAYS)
    sample = random.sample(customer_ids, min(500, len(customer_ids)))

    for day in range(HISTORY_DAYS):
        ts = datetime.utcnow() - timedelta(days=day)
        records = []
        for cid in sample:
            records.append((
                cid,
                "total_orders",
                json.dumps(random.randint(0, 100 - day)),
                ts,
            ))
            records.append((
                cid,
                "total_spend",
                json.dumps(round(random.uniform(0, 5000 - day * 10), 2)),
                ts,
            ))

        await conn.executemany(
            """
            INSERT INTO feature_values (entity_key, feature_name, value, event_timestamp)
            VALUES ($1, $2, $3, $4)
            """,
            records,
        )

    logger.info("historical_values_seeded")


async def seed_online_store(
    redis: Redis,
    conn: asyncpg.Connection,
    customer_ids: list[str],
) -> None:
    """Populate Redis online store with latest values."""
    logger.info("seeding_online_store")
    sample = random.sample(customer_ids, min(1000, len(customer_ids)))
    feature_names = [
        "total_orders", "total_spend", "avg_order_value",
        "order_count_7d", "page_views_7d",
    ]

    pipe = redis.pipeline()
    for cid in sample:
        for fname in feature_names:
            key = f"feature:{fname}:{cid}"
            val = json.dumps({
                "value": random.randint(0, 100),
                "event_timestamp": datetime.utcnow().isoformat(),
            })
            pipe.setex(key, 7200, val)
    await pipe.execute()
    logger.info("online_store_seeded", entities=len(sample))


async def main() -> None:
    from src.db.pool import create_pool, run_migrations
    from src.logging import setup_logging

    setup_logging(json_output=False)
    settings = get_settings()

    pool = await create_pool(settings)
    await run_migrations(pool)

    redis = Redis.from_url(settings.redis.url, decode_responses=True)

    async with pool.acquire() as conn:
        customer_ids = await seed_customers(conn)
        product_ids = await seed_products(conn)
        await seed_orders(conn, customer_ids, product_ids)
        await seed_historical_values(conn, customer_ids)
        await seed_online_store(redis, conn, customer_ids)

    await redis.aclose()
    await pool.close()
    logger.info("seeding_complete")


if __name__ == "__main__":
    asyncio.run(main())
