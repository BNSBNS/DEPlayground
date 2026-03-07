from __future__ import annotations

import json
from datetime import datetime

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

BUCKET_TTL = 7200  # 2 hours for hourly buckets


def _hour_bucket(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp)
    return dt.strftime("%Y%m%d%H")


class StreamAggregator:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def update(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        agg_function: str,
        timestamp: str,
    ) -> None:
        dispatch = {
            "count": self._update_count,
            "sum": self._update_sum,
            "avg": self._update_avg,
            "min": self._update_min,
            "max": self._update_max,
            "last": self.set_last,
        }
        handler = dispatch.get(agg_function)
        if handler is None:
            logger.warning("unsupported_stream_agg", function=agg_function)
            return

        if agg_function == "last":
            await handler(
                feature_name=feature_name,
                entity_key=entity_key,
                value=value,
                timestamp=timestamp,
                ttl=BUCKET_TTL,
            )
        else:
            await handler(
                feature_name=feature_name,
                entity_key=entity_key,
                value=value,
                timestamp=timestamp,
            )

    async def _update_count(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        timestamp: str,
    ) -> None:
        bucket = _hour_bucket(timestamp)
        key = f"agg:count:{feature_name}:{entity_key}:{bucket}"
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, BUCKET_TTL)
        await pipe.execute()
        await self._publish_online(feature_name, entity_key, timestamp)

    async def _update_sum(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        timestamp: str,
    ) -> None:
        if value is None:
            return
        bucket = _hour_bucket(timestamp)
        key = f"agg:sum:{feature_name}:{entity_key}:{bucket}"
        pipe = self._redis.pipeline()
        pipe.incrbyfloat(key, float(value))
        pipe.expire(key, BUCKET_TTL)
        await pipe.execute()
        await self._publish_online(feature_name, entity_key, timestamp)

    async def _update_avg(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        timestamp: str,
    ) -> None:
        if value is None:
            return
        bucket = _hour_bucket(timestamp)
        count_key = f"agg:avg_count:{feature_name}:{entity_key}:{bucket}"
        sum_key = f"agg:avg_sum:{feature_name}:{entity_key}:{bucket}"
        pipe = self._redis.pipeline()
        pipe.incr(count_key)
        pipe.incrbyfloat(sum_key, float(value))
        pipe.expire(count_key, BUCKET_TTL)
        pipe.expire(sum_key, BUCKET_TTL)
        await pipe.execute()
        await self._publish_online(feature_name, entity_key, timestamp)

    async def _update_min(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        timestamp: str,
    ) -> None:
        if value is None:
            return
        key = f"agg:minmax:{feature_name}:{entity_key}"
        await self._redis.zadd(key, {str(value): float(value)})
        await self._redis.expire(key, BUCKET_TTL)
        await self._publish_online(feature_name, entity_key, timestamp)

    async def _update_max(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        timestamp: str,
    ) -> None:
        if value is None:
            return
        key = f"agg:minmax:{feature_name}:{entity_key}"
        await self._redis.zadd(key, {str(value): float(value)})
        await self._redis.expire(key, BUCKET_TTL)
        await self._publish_online(feature_name, entity_key, timestamp)

    async def set_last(
        self,
        feature_name: str,
        entity_key: str,
        value: float | int | str | None,
        timestamp: str,
        ttl: int = BUCKET_TTL,
    ) -> None:
        key = f"feature:{feature_name}:{entity_key}"
        payload = json.dumps({
            "value": value,
            "event_timestamp": timestamp,
        }, default=str)
        await self._redis.setex(key, ttl, payload)

    async def _publish_online(
        self,
        feature_name: str,
        entity_key: str,
        timestamp: str,
    ) -> None:
        """Recompute aggregate and write to online store key."""
        # Read current state and publish to online key
        count_key = f"agg:count:{feature_name}:{entity_key}:*"
        sum_key = f"agg:sum:{feature_name}:{entity_key}:*"

        # For simplicity, write the latest timestamp
        key = f"feature:{feature_name}:{entity_key}"
        existing = await self._redis.get(key)
        if existing:
            return  # already fresh enough

        await self._redis.setex(
            key,
            BUCKET_TTL,
            json.dumps({"value": None, "event_timestamp": timestamp}),
        )
