from __future__ import annotations

import asyncio
import json
from datetime import datetime

import structlog
from aiokafka import AIOKafkaConsumer
from redis.asyncio import Redis

from src.compute.stream.aggregations import StreamAggregator
from src.config import Settings
from src.models.features import FeatureDefinition

logger = structlog.get_logger(__name__)


class StreamComputeEngine:
    def __init__(
        self,
        settings: Settings,
        redis: Redis,
        features: list[FeatureDefinition],
    ) -> None:
        self._settings = settings
        self._redis = redis
        self._features = {f.name: f for f in features}
        self._aggregator = StreamAggregator(redis)
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        topics = {
            f.stream_source
            for f in self._features.values()
            if f.stream_source
        }
        if not topics:
            logger.warning("no_stream_sources_configured")
            return

        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self._settings.kafka.bootstrap_servers,
            group_id=self._settings.kafka.consumer_group,
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await self._consumer.start()
        self._running = True
        logger.info("stream_engine_started", topics=list(topics))

        try:
            await self._consume_loop()
        finally:
            await self._consumer.stop()
            logger.info("stream_engine_stopped")

    async def _consume_loop(self) -> None:
        assert self._consumer is not None
        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self._process_message(msg.topic, msg.value)
            except Exception:
                logger.exception(
                    "stream_message_error",
                    topic=msg.topic,
                    offset=msg.offset,
                )

    async def _process_message(self, topic: str, event: dict) -> None:  # type: ignore[type-arg]
        matching = [
            f for f in self._features.values()
            if f.stream_source == topic
        ]

        for feature in matching:
            entity_key = str(event.get(f"{feature.entity}_id", ""))
            if not entity_key:
                continue

            value = event.get("value", event.get(feature.name))
            timestamp = event.get("event_timestamp", datetime.utcnow().isoformat())

            if feature.aggregation:
                await self._aggregator.update(
                    feature_name=feature.name,
                    entity_key=entity_key,
                    value=value,
                    agg_function=feature.aggregation.function,
                    timestamp=timestamp,
                )
            else:
                # Simple last-value write
                await self._aggregator.set_last(
                    feature_name=feature.name,
                    entity_key=entity_key,
                    value=value,
                    timestamp=timestamp,
                    ttl=feature.freshness_sla_minutes * 60 * 2,
                )

    async def stop(self) -> None:
        self._running = False


async def run_stream_engine(settings: Settings, redis: Redis) -> None:
    """Entry point for stream worker."""
    from src.definitions.parser import parse_all_definitions
    from pathlib import Path

    defs_dir = Path("feature_definitions")
    features, _ = parse_all_definitions(defs_dir)
    stream_features = [f for f in features if f.stream_source]

    engine = StreamComputeEngine(settings, redis, stream_features)
    try:
        await engine.start()
    except asyncio.CancelledError:
        await engine.stop()
