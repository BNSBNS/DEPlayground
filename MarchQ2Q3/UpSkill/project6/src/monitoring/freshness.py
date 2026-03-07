from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog

from src.storage.offline_store import OfflineStore

logger = structlog.get_logger(__name__)


class FreshnessStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class FreshnessResult:
    def __init__(
        self,
        feature_name: str,
        latest_timestamp: datetime | None,
        sla_minutes: int,
        status: FreshnessStatus,
        lag_minutes: float | None,
    ) -> None:
        self.feature_name = feature_name
        self.latest_timestamp = latest_timestamp
        self.sla_minutes = sla_minutes
        self.status = status
        self.lag_minutes = lag_minutes

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "latest_timestamp": self.latest_timestamp.isoformat()
            if self.latest_timestamp
            else None,
            "sla_minutes": self.sla_minutes,
            "status": self.status.value,
            "lag_minutes": self.lag_minutes,
        }


class FreshnessMonitor:
    def __init__(self, offline_store: OfflineStore) -> None:
        self._store = offline_store

    async def check(
        self,
        feature_name: str,
        sla_minutes: int = 60,
    ) -> FreshnessResult:
        latest = await self._store.get_latest_timestamp(feature_name)
        now = datetime.utcnow()

        if latest is None:
            return FreshnessResult(
                feature_name=feature_name,
                latest_timestamp=None,
                sla_minutes=sla_minutes,
                status=FreshnessStatus.UNKNOWN,
                lag_minutes=None,
            )

        lag = (now - latest).total_seconds() / 60.0

        if lag <= sla_minutes:
            status = FreshnessStatus.OK
        elif lag <= sla_minutes * 2:
            status = FreshnessStatus.WARNING
        else:
            status = FreshnessStatus.CRITICAL

        result = FreshnessResult(
            feature_name=feature_name,
            latest_timestamp=latest,
            sla_minutes=sla_minutes,
            status=status,
            lag_minutes=round(lag, 2),
        )

        if status != FreshnessStatus.OK:
            logger.warning(
                "freshness_alert",
                feature=feature_name,
                status=status.value,
                lag_minutes=result.lag_minutes,
                sla_minutes=sla_minutes,
            )

        return result

    async def check_all(
        self,
        feature_slas: dict[str, int],
    ) -> list[FreshnessResult]:
        results: list[FreshnessResult] = []
        for fname, sla in feature_slas.items():
            result = await self.check(fname, sla)
            results.append(result)
        return results
