from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as aioredis

from src.aggregation.redis_agg import RedisAggregator
from src.consumers.base import consume_topic
from src.logging import get_logger
from src.models.events import ClickAction, ClickstreamEvent

log = get_logger(__name__)

TOPIC = "clickstream"

# Map click actions to aggregate fields
ACTION_METRIC_MAP: dict[ClickAction, str] = {
    ClickAction.PAGE_VIEW: "page_views",
    ClickAction.PRODUCT_VIEW: "product_views",
    ClickAction.ADD_TO_CART: "cart_additions",
    ClickAction.SEARCH: "searches",
}


class ClickstreamConsumer:
    """Consumes clickstream events, manages session state, updates activity aggregates."""

    def __init__(self, redis: aioredis.Redis, aggregator: RedisAggregator) -> None:
        self._redis = redis
        self._aggregator = aggregator

    async def _update_session(self, event: ClickstreamEvent) -> None:
        """Track session state in Redis with 30-minute TTL."""
        session_key = f"session:{event.session_id}"
        await self._redis.hincrby(session_key, "event_count", 1)
        await self._redis.hset(session_key, "last_action", event.action.value)
        await self._redis.hset(session_key, "customer_id", event.customer_id)
        await self._redis.expire(session_key, 1800)  # 30 min TTL

    async def handle(self, payload: dict[str, Any]) -> None:
        event = ClickstreamEvent.model_validate(payload)
        ts = event.timestamp.isoformat()

        await self._update_session(event)

        # Update customer activity
        metric_name = ACTION_METRIC_MAP.get(event.action)
        if metric_name:
            await self._aggregator.increment(
                metric=f"customer:{metric_name}",
                dimension=event.customer_id,
                timestamp=ts,
                amount=1,
            )

        # Update product performance for product-related actions
        if event.product_id and event.action in (
            ClickAction.PRODUCT_VIEW,
            ClickAction.ADD_TO_CART,
        ):
            metric = (
                "product:views"
                if event.action == ClickAction.PRODUCT_VIEW
                else "product:cart_adds"
            )
            await self._aggregator.increment(
                metric=metric,
                dimension=event.product_id,
                timestamp=ts,
                amount=1,
            )

        log.debug(
            "click_processed",
            session_id=event.session_id,
            action=event.action.value,
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
