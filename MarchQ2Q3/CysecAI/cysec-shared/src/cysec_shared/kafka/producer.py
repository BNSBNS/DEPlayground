"""Emit SecurityAlert messages to Kafka cysec.alerts topic.

Usage:
    emitter = AlertEmitter(bootstrap_servers="localhost:9092")
    await emitter.start()
    await emitter.emit(alert)
    await emitter.stop()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiokafka import AIOKafkaProducer

from cysec_shared.logging import get_logger

if TYPE_CHECKING:
    from cysec_shared.models.alerts import SecurityAlert

logger = get_logger(__name__)


class AlertEmitter:
    """Async Kafka producer for SecurityAlert messages."""

    def __init__(self, bootstrap_servers: str, topic: str = "cysec.alerts") -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        """Start the Kafka producer."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8"),
        )
        await self._producer.start()
        logger.info("alert_emitter_started", topic=self._topic)

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("alert_emitter_stopped")

    async def emit(self, alert: SecurityAlert) -> None:
        """Serialize and send a SecurityAlert to Kafka."""
        if not self._producer:
            raise RuntimeError("AlertEmitter not started. Call start() first.")

        payload = alert.model_dump_json()
        await self._producer.send_and_wait(self._topic, payload)
        logger.info(
            "alert_emitted",
            alert_id=alert.alert_id,
            severity=alert.severity,
            source=alert.source_project,
            rule=alert.rule_id,
        )
