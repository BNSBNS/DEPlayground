from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import structlog

from src.storage.online_store import OnlineStore

logger = structlog.get_logger(__name__)


class OnlineServingResult:
    def __init__(
        self,
        entity_key: str,
        features: dict[str, Any],
        stale_features: list[str],
    ) -> None:
        self.entity_key = entity_key
        self.features = features
        self.stale_features = stale_features

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_key": self.entity_key,
            "features": self.features,
            "stale_features": self.stale_features,
        }


class OnlineServingService:
    def __init__(
        self,
        online_store: OnlineStore,
        freshness_sla: dict[str, int] | None = None,
    ) -> None:
        self._store = online_store
        self._freshness_sla = freshness_sla or {}

    async def get_features(
        self,
        entity_key: str,
        feature_names: list[str],
    ) -> OnlineServingResult:
        raw = await self._store.get_many(feature_names, entity_key)
        now = datetime.utcnow()

        features: dict[str, Any] = {}
        stale: list[str] = []

        for fname in feature_names:
            entry = raw.get(fname)
            if entry is None:
                features[fname] = None
                stale.append(fname)
                continue

            features[fname] = entry.get("value")

            # Check staleness
            sla_minutes = self._freshness_sla.get(fname, 60)
            ts_str = entry.get("event_timestamp")
            if ts_str:
                event_ts = datetime.fromisoformat(ts_str)
                if now - event_ts > timedelta(minutes=sla_minutes):
                    stale.append(fname)

        return OnlineServingResult(
            entity_key=entity_key,
            features=features,
            stale_features=stale,
        )

    async def get_features_multi(
        self,
        entity_keys: list[str],
        feature_names: list[str],
    ) -> list[OnlineServingResult]:
        results: list[OnlineServingResult] = []
        for ek in entity_keys:
            result = await self.get_features(ek, feature_names)
            results.append(result)
        return results
