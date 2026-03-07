from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.logging import get_logger
from src.models.aggregates import AnomalyFlag, AnomalySeverity

log = get_logger(__name__)

# Rule thresholds
ORDER_AMOUNT_MULTIPLIER = 3.0
CLICKS_PER_MINUTE_THRESHOLD = 100
PAYMENT_FAILURE_THRESHOLD = 3


class AnomalyDetector:
    """Cross-topic anomaly detection with configurable rules."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def detect_all(self) -> list[AnomalyFlag]:
        """Run all anomaly detection rules and return any flags."""
        anomalies: list[AnomalyFlag] = []
        anomalies.extend(await self._detect_high_value_orders())
        anomalies.extend(await self._detect_click_floods())
        anomalies.extend(await self._detect_payment_failure_spikes())
        return anomalies

    async def _detect_high_value_orders(self) -> list[AnomalyFlag]:
        """Flag orders that exceed 3x the running average."""
        anomalies: list[AnomalyFlag] = []
        avg_raw = await self._redis.get("stats:avg_order_value")
        if avg_raw is None:
            return anomalies

        avg_value = float(avg_raw.decode() if isinstance(avg_raw, bytes) else avg_raw)
        threshold = avg_value * ORDER_AMOUNT_MULTIPLIER

        # Scan recent order amounts
        async for key in self._redis.scan_iter(match="order:*", count=50):
            data = await self._redis.hgetall(key)
            amount_raw = data.get(b"total_amount") or data.get("total_amount")
            if amount_raw is None:
                continue
            amount = float(
                amount_raw.decode() if isinstance(amount_raw, bytes) else amount_raw
            )
            if amount > threshold:
                order_key = key.decode() if isinstance(key, bytes) else key
                order_id = order_key.split(":", 1)[1]

                # Check if already flagged
                flagged = await self._redis.get(f"flagged:order:{order_id}")
                if flagged:
                    continue
                await self._redis.set(f"flagged:order:{order_id}", "1", ex=3600)

                anomalies.append(
                    AnomalyFlag(
                        anomaly_id=str(uuid.uuid4()),
                        rule_name="high_value_order",
                        severity=AnomalySeverity.MEDIUM,
                        entity_type="order",
                        entity_id=order_id,
                        metric_name="order_amount",
                        metric_value=amount,
                        threshold=threshold,
                        description=(
                            f"Order {order_id} amount ${amount:.2f} exceeds "
                            f"{ORDER_AMOUNT_MULTIPLIER}x avg (${avg_value:.2f})"
                        ),
                    )
                )
        return anomalies

    async def _detect_click_floods(self) -> list[AnomalyFlag]:
        """Flag sessions with > 100 clicks per minute."""
        anomalies: list[AnomalyFlag] = []

        async for key in self._redis.scan_iter(match="session:*", count=100):
            data = await self._redis.hgetall(key)
            count_raw = data.get(b"event_count") or data.get("event_count")
            if count_raw is None:
                continue
            count = int(
                count_raw.decode() if isinstance(count_raw, bytes) else count_raw
            )
            if count > CLICKS_PER_MINUTE_THRESHOLD:
                session_key = key.decode() if isinstance(key, bytes) else key
                session_id = session_key.split(":", 1)[1]

                flagged = await self._redis.get(f"flagged:session:{session_id}")
                if flagged:
                    continue
                await self._redis.set(f"flagged:session:{session_id}", "1", ex=1800)

                customer_raw = data.get(b"customer_id") or data.get("customer_id")
                customer_id = (
                    customer_raw.decode()
                    if isinstance(customer_raw, bytes)
                    else (customer_raw or "unknown")
                )

                anomalies.append(
                    AnomalyFlag(
                        anomaly_id=str(uuid.uuid4()),
                        rule_name="click_flood",
                        severity=AnomalySeverity.HIGH,
                        entity_type="session",
                        entity_id=session_id,
                        metric_name="clicks_per_session",
                        metric_value=float(count),
                        threshold=float(CLICKS_PER_MINUTE_THRESHOLD),
                        description=(
                            f"Session {session_id} (customer {customer_id}) "
                            f"has {count} clicks (threshold: "
                            f"{CLICKS_PER_MINUTE_THRESHOLD})"
                        ),
                    )
                )
        return anomalies

    async def _detect_payment_failure_spikes(self) -> list[AnomalyFlag]:
        """Flag customers with 3+ consecutive payment failures."""
        anomalies: list[AnomalyFlag] = []

        async for key in self._redis.scan_iter(match="payment_failures:*", count=100):
            count_raw = await self._redis.get(key)
            if count_raw is None:
                continue
            count = int(
                count_raw.decode() if isinstance(count_raw, bytes) else count_raw
            )
            if count >= PAYMENT_FAILURE_THRESHOLD:
                key_str = key.decode() if isinstance(key, bytes) else key
                customer_id = key_str.split(":", 1)[1]

                flagged = await self._redis.get(f"flagged:payment:{customer_id}")
                if flagged:
                    continue
                await self._redis.set(f"flagged:payment:{customer_id}", "1", ex=3600)

                anomalies.append(
                    AnomalyFlag(
                        anomaly_id=str(uuid.uuid4()),
                        rule_name="consecutive_payment_failures",
                        severity=AnomalySeverity.HIGH,
                        entity_type="customer",
                        entity_id=customer_id,
                        metric_name="consecutive_failures",
                        metric_value=float(count),
                        threshold=float(PAYMENT_FAILURE_THRESHOLD),
                        description=(
                            f"Customer {customer_id} has {count} consecutive "
                            f"payment failures"
                        ),
                    )
                )
        return anomalies

    # --- Static rule helpers for unit testing ---

    @staticmethod
    def is_high_value_order(amount: float, avg_value: float) -> bool:
        """Check if an order amount exceeds the threshold."""
        return amount > avg_value * ORDER_AMOUNT_MULTIPLIER

    @staticmethod
    def is_click_flood(click_count: int) -> bool:
        """Check if a session's click count exceeds the threshold."""
        return click_count > CLICKS_PER_MINUTE_THRESHOLD

    @staticmethod
    def is_payment_failure_spike(failure_count: int) -> bool:
        """Check if consecutive payment failures exceed the threshold."""
        return failure_count >= PAYMENT_FAILURE_THRESHOLD
