from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from src.models.features import FeatureDefinition, FeatureSet

logger = structlog.get_logger(__name__)


class FeatureCatalog:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_feature(self, feature: FeatureDefinition) -> FeatureDefinition:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO feature_definitions
                    (name, feature_set, entity, value_type, description, owner, tags,
                     batch_source, stream_source, aggregation, transform,
                     freshness_sla_minutes, version, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (name) DO UPDATE SET
                    feature_set=$2, entity=$3, value_type=$4, description=$5,
                    owner=$6, tags=$7, batch_source=$8, stream_source=$9,
                    aggregation=$10, transform=$11, freshness_sla_minutes=$12,
                    version=$13, status=$14, updated_at=NOW()
                """,
                feature.name,
                feature.feature_set,
                feature.entity,
                feature.value_type.value,
                feature.description,
                feature.owner,
                feature.tags,
                feature.batch_source,
                feature.stream_source,
                json.dumps(feature.aggregation.model_dump()) if feature.aggregation else None,
                feature.transform,
                feature.freshness_sla_minutes,
                feature.version,
                feature.status.value,
            )
        logger.info("feature_created", name=feature.name)
        return feature

    async def get_feature(self, name: str) -> FeatureDefinition | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM feature_definitions WHERE name = $1", name
            )
        if row is None:
            return None
        return _row_to_feature(row)

    async def list_features(
        self,
        entity: str | None = None,
        feature_set: str | None = None,
        status: str | None = None,
    ) -> list[FeatureDefinition]:
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if entity:
            conditions.append(f"entity = ${idx}")
            params.append(entity)
            idx += 1
        if feature_set:
            conditions.append(f"feature_set = ${idx}")
            params.append(feature_set)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM feature_definitions {where} ORDER BY name"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [_row_to_feature(r) for r in rows]

    async def search_features(
        self,
        query: str,
        owner: str | None = None,
        tag: str | None = None,
    ) -> list[FeatureDefinition]:
        conditions = ["(name ILIKE $1 OR description ILIKE $1)"]
        params: list[Any] = [f"%{query}%"]
        idx = 2

        if owner:
            conditions.append(f"owner = ${idx}")
            params.append(owner)
            idx += 1
        if tag:
            conditions.append(f"${idx} = ANY(tags)")
            params.append(tag)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}"
        sql = f"SELECT * FROM feature_definitions {where} ORDER BY name"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        return [_row_to_feature(r) for r in rows]

    async def create_feature_set(self, fs: FeatureSet) -> FeatureSet:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO feature_sets (name, entity, features, batch_source, stream_source, schedule)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (name) DO UPDATE SET
                    entity=$2, features=$3, batch_source=$4,
                    stream_source=$5, schedule=$6, updated_at=NOW()
                """,
                fs.name,
                fs.entity,
                fs.features,
                fs.batch_source,
                fs.stream_source,
                fs.schedule,
            )
        logger.info("feature_set_created", name=fs.name)
        return fs

    async def get_feature_set(self, name: str) -> FeatureSet | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM feature_sets WHERE name = $1", name)
        if row is None:
            return None
        return FeatureSet(
            name=row["name"],
            entity=row["entity"],
            features=list(row["features"]),
            batch_source=row["batch_source"],
            stream_source=row["stream_source"],
            schedule=row["schedule"],
        )

    async def list_feature_sets(self) -> list[FeatureSet]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM feature_sets ORDER BY name")
        return [
            FeatureSet(
                name=r["name"],
                entity=r["entity"],
                features=list(r["features"]),
                batch_source=r["batch_source"],
                stream_source=r["stream_source"],
                schedule=r["schedule"],
            )
            for r in rows
        ]


def _row_to_feature(row: asyncpg.Record) -> FeatureDefinition:
    agg_raw = row["aggregation"]
    agg = None
    if agg_raw:
        agg_data = json.loads(agg_raw) if isinstance(agg_raw, str) else agg_raw
        from src.models.features import AggSpec

        agg = AggSpec(**agg_data)

    return FeatureDefinition(
        name=row["name"],
        feature_set=row["feature_set"],
        entity=row["entity"],
        value_type=row["value_type"],
        description=row["description"],
        owner=row["owner"],
        tags=list(row["tags"]) if row["tags"] else [],
        batch_source=row["batch_source"],
        stream_source=row["stream_source"],
        aggregation=agg,
        transform=row["transform"],
        freshness_sla_minutes=row["freshness_sla_minutes"],
        version=row["version"],
        status=row["status"],
    )
