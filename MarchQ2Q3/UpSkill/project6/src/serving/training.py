from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog

from src.models.training import TrainingDataset
from src.serving.pit_join import build_pit_join_query
from src.storage.offline_store import OfflineStore

logger = structlog.get_logger(__name__)


class TrainingDatasetBuilder:
    def __init__(self, offline_store: OfflineStore) -> None:
        self._store = offline_store

    async def build(
        self,
        name: str,
        entity_type: str,
        entity_keys: list[str],
        feature_names: list[str],
        timestamps: list[datetime] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[TrainingDataset, list[dict[str, Any]]]:
        """Build a training dataset with PIT-correct feature values."""
        if timestamps and len(timestamps) == len(entity_keys):
            entity_df = [
                {"entity_key": ek, "event_timestamp": ts}
                for ek, ts in zip(entity_keys, timestamps)
            ]
        else:
            as_of = end_time or datetime.utcnow()
            entity_df = [
                {"entity_key": ek, "event_timestamp": as_of}
                for ek in entity_keys
            ]

        rows: list[dict[str, Any]] = []
        for entry in entity_df:
            ek = entry["entity_key"]
            as_of = entry["event_timestamp"]
            feature_values = await self._store.get_entity_features_pit(
                ek, feature_names, as_of
            )
            row = {"entity_key": ek, "event_timestamp": as_of, **feature_values}
            rows.append(row)

        dataset = TrainingDataset(
            id=str(uuid.uuid4()),
            name=name,
            entity_type=entity_type,
            features=feature_names,
            entity_df_ref=f"memory://{name}",
            row_count=len(rows),
        )

        logger.info(
            "training_dataset_built",
            name=name,
            rows=len(rows),
            features=len(feature_names),
        )
        return dataset, rows

    async def build_from_sql(
        self,
        name: str,
        entity_type: str,
        feature_names: list[str],
        entity_join_key: str,
        start_time: datetime,
        end_time: datetime,
    ) -> str:
        """Return the PIT join SQL query for external execution."""
        return build_pit_join_query(
            feature_names=feature_names,
            entity_join_key=entity_join_key,
            start_time=start_time,
            end_time=end_time,
        )
