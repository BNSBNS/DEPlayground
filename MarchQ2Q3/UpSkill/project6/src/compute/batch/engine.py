from __future__ import annotations

import json
from datetime import datetime

import asyncpg
import structlog
from redis.asyncio import Redis

from src.models.features import FeatureDefinition, FeatureSet

logger = structlog.get_logger(__name__)


class BatchComputeEngine:
    def __init__(self, pool: asyncpg.Pool, redis: Redis) -> None:
        self._pool = pool
        self._redis = redis

    async def compute_feature_set(
        self,
        feature_set: FeatureSet,
        features: list[FeatureDefinition],
        as_of: datetime | None = None,
    ) -> int:
        """Compute all features in a feature set from batch source."""
        if not feature_set.batch_source:
            logger.warning("no_batch_source", feature_set=feature_set.name)
            return 0

        total_rows = 0
        for feature in features:
            if feature.feature_set != feature_set.name:
                continue
            rows = await self._compute_feature(feature, feature_set, as_of)
            total_rows += rows

        logger.info(
            "batch_compute_complete",
            feature_set=feature_set.name,
            total_rows=total_rows,
        )
        return total_rows

    async def _compute_feature(
        self,
        feature: FeatureDefinition,
        feature_set: FeatureSet,
        as_of: datetime | None = None,
    ) -> int:
        """Compute a single feature via SQL aggregation."""
        as_of = as_of or datetime.utcnow()
        entity_col = f"{feature.entity}_id"

        if feature.aggregation:
            agg_fn = feature.aggregation.function.upper()
            window = feature.aggregation.window
            filter_clause = ""
            if feature.aggregation.filter:
                filter_clause = f"AND {feature.aggregation.filter}"

            query = f"""
                SELECT {entity_col} AS entity_key,
                       {agg_fn}(value) AS computed_value
                FROM {feature_set.batch_source}
                WHERE event_timestamp >= $1::timestamptz - interval '{window}'
                  AND event_timestamp <= $1::timestamptz
                  {filter_clause}
                GROUP BY {entity_col}
            """
        elif feature.transform:
            query = f"""
                SELECT {entity_col} AS entity_key,
                       {feature.transform} AS computed_value
                FROM {feature_set.batch_source}
                WHERE event_timestamp <= $1::timestamptz
                GROUP BY {entity_col}
            """
        else:
            query = f"""
                SELECT DISTINCT ON ({entity_col})
                       {entity_col} AS entity_key,
                       {feature.name} AS computed_value
                FROM {feature_set.batch_source}
                WHERE event_timestamp <= $1::timestamptz
                ORDER BY {entity_col}, event_timestamp DESC
            """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, as_of)

            # Write to offline store
            for row in rows:
                await conn.execute(
                    """
                    INSERT INTO feature_values (entity_key, feature_name, value, event_timestamp)
                    VALUES ($1, $2, $3, $4)
                    """,
                    str(row["entity_key"]),
                    feature.name,
                    json.dumps(row["computed_value"], default=str),
                    as_of,
                )

            # Write to online store (Redis)
            pipe = self._redis.pipeline()
            ttl = feature.freshness_sla_minutes * 60 * 2
            for row in rows:
                key = f"feature:{feature.name}:{row['entity_key']}"
                payload = json.dumps({
                    "value": row["computed_value"],
                    "event_timestamp": as_of.isoformat(),
                }, default=str)
                pipe.setex(key, ttl, payload)
            await pipe.execute()

        logger.info(
            "feature_computed",
            feature=feature.name,
            rows=len(rows),
        )
        return len(rows)
