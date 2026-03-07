from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from src.models.features import FeatureValue

logger = structlog.get_logger(__name__)


class OfflineStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_batch(self, values: list[FeatureValue]) -> int:
        if not values:
            return 0

        async with self._pool.acquire() as conn:
            records = [
                (
                    v.entity_key,
                    v.feature_name,
                    json.dumps(v.value, default=str),
                    v.event_timestamp,
                    v.created_timestamp,
                )
                for v in values
            ]
            await conn.executemany(
                """
                INSERT INTO feature_values
                    (entity_key, feature_name, value, event_timestamp, created_timestamp)
                VALUES ($1, $2, $3, $4, $5)
                """,
                records,
            )

        logger.info("offline_store_write", count=len(values))
        return len(values)

    async def get_point_in_time(
        self,
        feature_name: str,
        entity_key: str,
        as_of: datetime,
    ) -> FeatureValue | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT DISTINCT ON (entity_key)
                    entity_key, feature_name, value, event_timestamp, created_timestamp
                FROM feature_values
                WHERE feature_name = $1
                  AND entity_key = $2
                  AND event_timestamp <= $3
                ORDER BY entity_key, event_timestamp DESC
                """,
                feature_name,
                entity_key,
                as_of,
            )

        if row is None:
            return None

        return FeatureValue(
            entity_key=row["entity_key"],
            feature_name=row["feature_name"],
            value=json.loads(row["value"]) if row["value"] else None,
            event_timestamp=row["event_timestamp"],
            created_timestamp=row["created_timestamp"],
        )

    async def get_feature_history(
        self,
        feature_name: str,
        entity_key: str,
        start: datetime,
        end: datetime,
    ) -> list[FeatureValue]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_key, feature_name, value, event_timestamp, created_timestamp
                FROM feature_values
                WHERE feature_name = $1
                  AND entity_key = $2
                  AND event_timestamp BETWEEN $3 AND $4
                ORDER BY event_timestamp
                """,
                feature_name,
                entity_key,
                start,
                end,
            )

        return [
            FeatureValue(
                entity_key=r["entity_key"],
                feature_name=r["feature_name"],
                value=json.loads(r["value"]) if r["value"] else None,
                event_timestamp=r["event_timestamp"],
                created_timestamp=r["created_timestamp"],
            )
            for r in rows
        ]

    async def get_latest_timestamp(self, feature_name: str) -> datetime | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(event_timestamp) AS latest
                FROM feature_values
                WHERE feature_name = $1
                """,
                feature_name,
            )
        return row["latest"] if row else None

    async def get_entity_features_pit(
        self,
        entity_key: str,
        feature_names: list[str],
        as_of: datetime,
    ) -> dict[str, Any]:
        """Get multiple features for an entity at a point in time."""
        result: dict[str, Any] = {}
        for fname in feature_names:
            fv = await self.get_point_in_time(fname, entity_key, as_of)
            result[fname] = fv.value if fv else None
        return result
