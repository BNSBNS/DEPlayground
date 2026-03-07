"""Real-time simulation for the feature store.

- 10-50 events/sec random stream events
- Every 5 min: inject drift into feature distributions
- Every 15 min: trigger batch compute runs
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime

import structlog
from redis.asyncio import Redis

from src.config import get_settings
from src.logging import setup_logging

logger = structlog.get_logger(__name__)


async def emit_stream_events(redis: Redis, rate_range: tuple[int, int] = (10, 50)) -> None:
    """Emit synthetic stream events at a configurable rate."""
    customer_ids = [f"CUST-{i:04d}" for i in range(500)]
    product_ids = [f"PROD-{i:04d}" for i in range(200)]
    event_types = ["page_view", "add_to_cart", "search", "purchase", "click"]

    while True:
        rate = random.randint(*rate_range)
        batch_size = min(rate, 50)
        interval = 1.0 / max(rate, 1)

        for _ in range(batch_size):
            event = {
                "customer_id": random.choice(customer_ids),
                "product_id": random.choice(product_ids),
                "event_type": random.choice(event_types),
                "value": round(random.uniform(1, 500), 2),
                "event_timestamp": datetime.utcnow().isoformat(),
            }

            # Publish to Redis pub/sub as lightweight stream substitute
            await redis.publish("stream:events", json.dumps(event))
            await asyncio.sleep(interval)


async def inject_drift(redis: Redis, interval_minutes: int = 5) -> None:
    """Periodically shift feature distributions to simulate drift."""
    while True:
        await asyncio.sleep(interval_minutes * 60)

        logger.info("injecting_drift")
        # Shift some customer feature values to simulate distribution change
        drift_features = ["total_spend", "avg_order_value", "order_count_7d"]
        for fname in drift_features:
            # Modify a sample of online store values
            for i in range(100):
                cid = f"CUST-{random.randint(0, 499):04d}"
                key = f"feature:{fname}:{cid}"

                current = await redis.get(key)
                if current:
                    data = json.loads(current)
                    original = data.get("value", 0)
                    if isinstance(original, (int, float)):
                        # Apply drift: shift mean by 20-50%
                        shift = random.uniform(0.2, 0.5) * original
                        data["value"] = round(original + shift, 2)
                        data["event_timestamp"] = datetime.utcnow().isoformat()
                        await redis.setex(key, 7200, json.dumps(data))

        logger.info("drift_injected", features=drift_features)


async def trigger_batch_runs(interval_minutes: int = 15) -> None:
    """Periodically trigger batch compute via API."""
    import httpx

    settings = get_settings()
    base_url = f"http://localhost:{settings.api.port}"

    while True:
        await asyncio.sleep(interval_minutes * 60)
        logger.info("triggering_batch_compute")

        feature_sets = [
            "customer_order_features",
            "customer_activity_features",
            "product_features",
            "order_features",
        ]

        async with httpx.AsyncClient() as client:
            for fs_name in feature_sets:
                try:
                    resp = await client.post(
                        f"{base_url}/api/v1/compute/batch/trigger",
                        json={"feature_set": fs_name},
                        timeout=120.0,
                    )
                    logger.info(
                        "batch_trigger_result",
                        feature_set=fs_name,
                        status=resp.status_code,
                    )
                except Exception:
                    logger.exception("batch_trigger_failed", feature_set=fs_name)


async def log_metrics(redis: Redis, interval_seconds: int = 30) -> None:
    """Periodically log simulation metrics."""
    while True:
        await asyncio.sleep(interval_seconds)
        info = await redis.info("stats")
        logger.info(
            "simulation_metrics",
            connected_clients=info.get("connected_clients", 0),
            total_commands=info.get("total_commands_processed", 0),
        )


async def main() -> None:
    setup_logging(json_output=False)
    settings = get_settings()
    redis = Redis.from_url(settings.redis.url, decode_responses=True)

    logger.info("simulation_started")

    try:
        await asyncio.gather(
            emit_stream_events(redis),
            inject_drift(redis),
            trigger_batch_runs(),
            log_metrics(redis),
        )
    except asyncio.CancelledError:
        logger.info("simulation_stopped")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
