from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from src.storage.offline_store import OfflineStore

logger = structlog.get_logger(__name__)


class BatchServingService:
    def __init__(self, offline_store: OfflineStore) -> None:
        self._store = offline_store

    async def get_features(
        self,
        entity_keys: list[str],
        feature_names: list[str],
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get point-in-time correct features for a list of entity keys."""
        as_of = as_of or datetime.utcnow()
        results: list[dict[str, Any]] = []

        for ek in entity_keys:
            row: dict[str, Any] = {"entity_key": ek}
            features = await self._store.get_entity_features_pit(
                ek, feature_names, as_of
            )
            row.update(features)
            results.append(row)

        logger.info(
            "batch_serving_complete",
            entities=len(entity_keys),
            features=len(feature_names),
        )
        return results

    async def get_entity_dataframe(
        self,
        entity_df: list[dict[str, Any]],
        feature_names: list[str],
    ) -> list[dict[str, Any]]:
        """Join features to an entity DataFrame with per-row timestamps."""
        results: list[dict[str, Any]] = []

        for row in entity_df:
            ek = str(row.get("entity_key", ""))
            as_of = row.get("event_timestamp", datetime.utcnow())
            if isinstance(as_of, str):
                as_of = datetime.fromisoformat(as_of)

            features = await self._store.get_entity_features_pit(
                ek, feature_names, as_of
            )
            result = {**row, **features}
            results.append(result)

        return results
