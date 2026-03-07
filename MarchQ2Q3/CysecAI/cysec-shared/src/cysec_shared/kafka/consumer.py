"""Consume SecurityAlert messages from Kafka cysec.alerts topic.

Used by SecurityDataPipeline (SIEM) to ingest cross-project alerts.

Usage:
    consumer = AlertConsumer(bootstrap_servers="localhost:9092", group_id="siem")
    await consumer.start()
    async for alert in consumer.consume():
        process(alert)
    await consumer.stop()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiokafka import AIOKafkaConsumer

from cysec_shared.logging import get_logger
from cysec_shared.models.alerts import SecurityAlert

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


class AlertConsumer:
    """Async Kafka consumer for SecurityAlert messages."""

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str = "cysec-siem",
        topic: str = "cysec.alerts",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._group_id = group_id
        self._topic = topic
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Start the Kafka consumer."""
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            value_deserializer=lambda v: v.decode("utf-8"),
            auto_offset_reset="earliest",
        )
        await self._consumer.start()
        logger.info("alert_consumer_started", topic=self._topic, group=self._group_id)

    async def stop(self) -> None:
        """Stop the Kafka consumer."""
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            logger.info("alert_consumer_stopped")

    async def consume(self) -> AsyncIterator[SecurityAlert]:
        """Yield SecurityAlert objects from Kafka."""
        if not self._consumer:
            raise RuntimeError("AlertConsumer not started. Call start() first.")

        async for msg in self._consumer:
            try:
                alert = SecurityAlert.model_validate_json(msg.value)
                yield alert
            except Exception:
                logger.exception("alert_deserialize_failed", raw=msg.value[:200])
