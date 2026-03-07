from __future__ import annotations

import asyncio

import redis.asyncio as aioredis

from src.logging import get_logger
from src.models.aggregates import AnomalyFlag
from src.processors.anomaly_detector import AnomalyDetector

log = get_logger(__name__)


class AnomalyConsumer:
    """Cross-topic anomaly detection consumer.

    Polls the anomalies:pending Redis list and runs additional cross-topic
    detection rules periodically.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._detector = AnomalyDetector(redis)

    async def _process_pending_anomalies(self) -> None:
        """Drain pending anomalies from Redis list and persist."""
        while True:
            raw = await self._redis.lpop("anomalies:pending")
            if raw is None:
                break
            anomaly = AnomalyFlag.model_validate_json(
                raw.decode() if isinstance(raw, bytes) else raw
            )
            await self._persist_anomaly(anomaly)

    async def _persist_anomaly(self, anomaly: AnomalyFlag) -> None:
        """Store anomaly in Redis sorted set for quick retrieval."""
        key = f"anomaly:{anomaly.anomaly_id}"
        await self._redis.set(key, anomaly.model_dump_json(), ex=86400)
        await self._redis.zadd(
            "anomalies:timeline",
            {anomaly.anomaly_id: anomaly.detected_at.timestamp()},
        )
        log.info(
            "anomaly_persisted",
            anomaly_id=anomaly.anomaly_id,
            rule=anomaly.rule_name,
            severity=anomaly.severity.value,
        )

    async def _run_cross_topic_detection(self) -> None:
        """Run periodic cross-topic anomaly detection rules."""
        anomalies = await self._detector.detect_all()
        for anomaly in anomalies:
            await self._redis.rpush("anomalies:pending", anomaly.model_dump_json())

    async def run(self, shutdown_event: asyncio.Event | None = None) -> None:
        """Main loop: process pending anomalies + run detection every 30s."""
        log.info("anomaly_consumer_started")
        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    break
                await self._process_pending_anomalies()
                await self._run_cross_topic_detection()
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            log.info("anomaly_consumer_cancelled")
        finally:
            log.info("anomaly_consumer_stopped")
