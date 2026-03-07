from __future__ import annotations

import asyncio
from datetime import datetime

import structlog

from src.compute.batch.engine import BatchComputeEngine
from src.models.features import FeatureDefinition, FeatureSet

logger = structlog.get_logger(__name__)

SCHEDULE_INTERVALS: dict[str, int] = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}


class BatchScheduler:
    def __init__(self, engine: BatchComputeEngine) -> None:
        self._engine = engine
        self._schedules: dict[str, ScheduledJob] = {}
        self._running = False

    def register(
        self,
        feature_set: FeatureSet,
        features: list[FeatureDefinition],
    ) -> None:
        interval = SCHEDULE_INTERVALS.get(feature_set.schedule, 86400)
        self._schedules[feature_set.name] = ScheduledJob(
            feature_set=feature_set,
            features=features,
            interval_seconds=interval,
            last_run=None,
        )
        logger.info(
            "schedule_registered",
            feature_set=feature_set.name,
            schedule=feature_set.schedule,
            interval_seconds=interval,
        )

    async def run(self) -> None:
        self._running = True
        logger.info("batch_scheduler_started")

        while self._running:
            now = datetime.utcnow()
            for name, job in self._schedules.items():
                if job.is_due(now):
                    try:
                        rows = await self._engine.compute_feature_set(
                            job.feature_set, job.features
                        )
                        job.last_run = now
                        logger.info("scheduled_batch_complete", feature_set=name, rows=rows)
                    except Exception:
                        logger.exception("scheduled_batch_failed", feature_set=name)

            await asyncio.sleep(60)

    def stop(self) -> None:
        self._running = False
        logger.info("batch_scheduler_stopped")


class ScheduledJob:
    def __init__(
        self,
        feature_set: FeatureSet,
        features: list[FeatureDefinition],
        interval_seconds: int,
        last_run: datetime | None,
    ) -> None:
        self.feature_set = feature_set
        self.features = features
        self.interval_seconds = interval_seconds
        self.last_run = last_run

    def is_due(self, now: datetime) -> bool:
        if self.last_run is None:
            return True
        elapsed = (now - self.last_run).total_seconds()
        return elapsed >= self.interval_seconds
