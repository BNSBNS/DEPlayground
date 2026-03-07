from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class OnlineStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def write(
        self,
        feature_name: str,
        entity_key: str,
        value: Any,
        event_timestamp: datetime,
        ttl_seconds: int = 7200,
    ) -> None:
        key = f"feature:{feature_name}:{entity_key}"
        payload = json.dumps({
            "value": value,
            "event_timestamp": event_timestamp.isoformat(),
        }, default=str)
        await self._redis.setex(key, ttl_seconds, payload)

    async def get(
        self,
        feature_name: str,
        entity_key: str,
    ) -> dict[str, Any] | None:
        key = f"feature:{feature_name}:{entity_key}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def get_many(
        self,
        feature_names: list[str],
        entity_key: str,
    ) -> dict[str, dict[str, Any] | None]:
        """Pipeline MGET for batch reads."""
        keys = [f"feature:{fname}:{entity_key}" for fname in feature_names]
        values = await self._redis.mget(keys)

        result: dict[str, dict[str, Any] | None] = {}
        for fname, raw in zip(feature_names, values):
            if raw is None:
                result[fname] = None
            else:
                result[fname] = json.loads(raw)
        return result

    async def get_multi_entity(
        self,
        feature_names: list[str],
        entity_keys: list[str],
    ) -> dict[str, dict[str, dict[str, Any] | None]]:
        """Get features for multiple entities using pipeline."""
        pipe = self._redis.pipeline()
        key_map: list[tuple[str, str]] = []

        for ek in entity_keys:
            for fname in feature_names:
                key = f"feature:{fname}:{ek}"
                pipe.get(key)
                key_map.append((ek, fname))

        values = await pipe.execute()

        result: dict[str, dict[str, dict[str, Any] | None]] = {}
        for (ek, fname), raw in zip(key_map, values):
            if ek not in result:
                result[ek] = {}
            result[ek][fname] = json.loads(raw) if raw else None

        return result

    async def delete(self, feature_name: str, entity_key: str) -> None:
        key = f"feature:{feature_name}:{entity_key}"
        await self._redis.delete(key)
