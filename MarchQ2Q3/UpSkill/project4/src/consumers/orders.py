from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as aioredis

from src.aggregation.redis_agg import RedisAggregator
from src.consumers.base import consume_topic
from src.logging import get_logger
from src.models.events import OrderEvent, OrderStatus
from src.processors.enricher import Enricher

log = get_logger(__name__)

TOPIC = "orders"


class OrderConsumer:
    """Consumes order events, enriches with customer data, updates sales aggregates."""

    def __init__(self, redis: aioredis.Redis, aggregator: RedisAggregator) -> None:
        self._redis = redis
        self._aggregator = aggregator
        self._enricher = Enricher(redis)

    async def handle(self, payload: dict[str, Any]) -> None:
        event = OrderEvent.model_validate(payload)
        customer = await self._enricher.get_customer(event.customer_id)
        region = customer["region"] if customer else event.region

        ts = event.timestamp.isoformat()

        # Update real-time sales aggregation
        await self._aggregator.increment(
            metric="sales:orders",
            dimension=region,
            timestamp=ts,
            amount=1,
        )
        await self._aggregator.increment_float(
            metric="sales:revenue",
            dimension=region,
            timestamp=ts,
            amount=float(event.total_amount),
        )

        if event.status == OrderStatus.CANCELLED:
            await self._aggregator.increment(
                metric="sales:cancelled",
                dimension=region,
                timestamp=ts,
                amount=1,
            )

        # Track unique customers via HyperLogLog-style set
        await self._redis.sadd(
            f"agg:sales:customers:{region}:{ts[:16]}", event.customer_id
        )

        # Store order for payment correlation
        await self._redis.hset(
            f"order:{event.order_id}",
            mapping={
                "customer_id": event.customer_id,
                "total_amount": str(event.total_amount),
                "status": event.status.value,
                "region": region,
            },
        )
        await self._redis.expire(f"order:{event.order_id}", 7200)

        log.info(
            "order_processed",
            order_id=event.order_id,
            status=event.status.value,
            amount=str(event.total_amount),
        )

    async def run(
        self, group_id: str, shutdown_event: asyncio.Event | None = None
    ) -> None:
        await consume_topic(
            topic=TOPIC,
            group_id=group_id,
            handler=self.handle,
            redis=self._redis,
            shutdown_event=shutdown_event,
        )
