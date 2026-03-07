from __future__ import annotations

import json

from aiokafka import AIOKafkaProducer
from pydantic import BaseModel

from src.config import settings
from src.logging import get_logger

log = get_logger(__name__)


class EventProducer:
    """Async Kafka producer for Pydantic event models."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()
        log.info("kafka_producer_started")

    async def produce(self, topic: str, key: str, event: BaseModel) -> None:
        if self._producer is None:
            raise RuntimeError("Producer not started")
        payload = event.model_dump(mode="json")
        await self._producer.send_and_wait(topic=topic, key=key, value=payload)
        log.debug("event_produced", topic=topic, key=key)

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            log.info("kafka_producer_stopped")
