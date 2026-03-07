from __future__ import annotations

import asyncio
import uuid
from typing import Any

import redis.asyncio as aioredis

from src.aggregation.redis_agg import RedisAggregator
from src.consumers.base import consume_topic
from src.logging import get_logger
from src.models.aggregates import AnomalyFlag, AnomalySeverity
from src.models.events import PaymentEvent, PaymentStatus

log = get_logger(__name__)

TOPIC = "payments"
FAILURE_WINDOW_KEY = "payment_failures:{customer_id}"
CONSECUTIVE_FAILURE_THRESHOLD = 3


class PaymentConsumer:
    """Consumes payment events, correlates with orders, detects consecutive failures."""

    def __init__(self, redis: aioredis.Redis, aggregator: RedisAggregator) -> None:
        self._redis = redis
        self._aggregator = aggregator

    async def _check_consecutive_failures(
        self, event: PaymentEvent
    ) -> AnomalyFlag | None:
        """Detect 3+ consecutive payment failures for a customer."""
        key = f"payment_failures:{event.customer_id}"

        if event.status == PaymentStatus.FAILED:
            count = await self._redis.incr(key)
            await self._redis.expire(key, 3600)

            if count >= CONSECUTIVE_FAILURE_THRESHOLD:
                return AnomalyFlag(
                    anomaly_id=str(uuid.uuid4()),
                    rule_name="consecutive_payment_failures",
                    severity=AnomalySeverity.HIGH,
                    entity_type="customer",
                    entity_id=event.customer_id,
                    metric_name="consecutive_failures",
                    metric_value=float(count),
                    threshold=float(CONSECUTIVE_FAILURE_THRESHOLD),
                    description=(
                        f"Customer {event.customer_id} has {count} consecutive "
                        f"payment failures"
                    ),
                )
        else:
            # Reset on successful payment
            await self._redis.delete(key)

        return None

    async def _correlate_with_order(self, event: PaymentEvent) -> dict[str, str]:
        """Look up the original order for this payment."""
        order_data = await self._redis.hgetall(f"order:{event.order_id}")
        return {
            k.decode() if isinstance(k, bytes) else k: (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in order_data.items()
        }

    async def handle(self, payload: dict[str, Any]) -> None:
        event = PaymentEvent.model_validate(payload)
        ts = event.timestamp.isoformat()

        # Correlate with order
        order_data = await self._correlate_with_order(event)
        region = order_data.get("region", "unknown")

        # Update payment aggregations
        await self._aggregator.increment(
            metric=f"payments:{event.status.value}",
            dimension=region,
            timestamp=ts,
            amount=1,
        )

        if event.status == PaymentStatus.CAPTURED:
            await self._aggregator.increment_float(
                metric="payments:captured_amount",
                dimension=region,
                timestamp=ts,
                amount=float(event.amount),
            )

        # Check for consecutive failures
        anomaly = await self._check_consecutive_failures(event)
        if anomaly:
            await self._redis.rpush(
                "anomalies:pending",
                anomaly.model_dump_json(),
            )
            log.warning(
                "anomaly_detected",
                rule=anomaly.rule_name,
                customer_id=event.customer_id,
                failures=anomaly.metric_value,
            )

        log.debug(
            "payment_processed",
            payment_id=event.payment_id,
            status=event.status.value,
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
