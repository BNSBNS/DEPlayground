from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer

from src.config import settings
from src.logging import get_logger
from src.metrics import CONSUMER_LAG, EVENTS_PROCESSED, HANDLER_ERRORS

log = get_logger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]

# How often to sample consumer lag (every N messages).
# Avoids calling end_offsets() on every single message.
_LAG_CHECK_EVERY = 50


async def _is_duplicate(redis: aioredis.Redis, event_id: str) -> bool:
    """Check + set dedup key in Redis. Returns True if already processed."""
    key = f"dedup:{event_id}"
    was_set = await redis.set(key, "1", nx=True, ex=3600)
    return was_set is None


async def _update_lag(consumer: AIOKafkaConsumer, topic: str, group_id: str) -> None:
    """Compute consumer lag and publish to Prometheus CONSUMER_LAG gauge.

    Lag = sum(end_offset - committed_offset) across all assigned partitions.
    A steadily rising lag means the consumer can't keep up with the producers.
    """
    try:
        partitions = consumer.assignment()
        if not partitions:
            return
        end_offsets = await consumer.end_offsets(partitions)
        lag = sum(
            end_offsets[tp] - (await consumer.committed(tp) or 0)
            for tp in partitions
        )
        CONSUMER_LAG.labels(topic=topic, group_id=group_id).set(lag)
        log.debug("consumer_lag_updated", topic=topic, lag=lag)
    except Exception:
        log.debug("consumer_lag_check_failed", topic=topic)


async def consume_topic(
    topic: str,
    group_id: str,
    handler: MessageHandler,
    redis: aioredis.Redis,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    """Reusable consumer loop: manual commit, dedup, graceful shutdown, Prometheus metrics."""
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka.bootstrap_servers,
        group_id=group_id,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=False,
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info("consumer_started", topic=topic, group_id=group_id)

    msg_count = 0
    try:
        async for msg in consumer:
            if shutdown_event and shutdown_event.is_set():
                break

            payload: dict[str, Any] = msg.value
            event_id = payload.get("event_id", "")

            if event_id and await _is_duplicate(redis, event_id):
                log.debug("duplicate_skipped", event_id=event_id, topic=topic)
                await consumer.commit()
                continue

            try:
                await handler(payload)
                await consumer.commit()
                EVENTS_PROCESSED.labels(topic=topic).inc()
                msg_count += 1
                if msg_count % _LAG_CHECK_EVERY == 0:
                    await _update_lag(consumer, topic, group_id)
            except Exception:
                HANDLER_ERRORS.labels(topic=topic).inc()
                log.exception("handler_error", topic=topic, event_id=event_id)
    finally:
        await consumer.stop()
        log.info("consumer_stopped", topic=topic)
