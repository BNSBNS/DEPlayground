from __future__ import annotations

from datetime import datetime, timedelta

import structlog

from src.compute.batch.engine import BatchComputeEngine
from src.models.features import FeatureDefinition, FeatureSet

logger = structlog.get_logger(__name__)


class BackfillJob:
    def __init__(self, engine: BatchComputeEngine) -> None:
        self._engine = engine

    async def run(
        self,
        feature_set: FeatureSet,
        features: list[FeatureDefinition],
        start_date: datetime,
        end_date: datetime | None = None,
        window_hours: int = 24,
    ) -> int:
        """Compute historical feature values over a date range."""
        end_date = end_date or datetime.utcnow()
        window = timedelta(hours=window_hours)
        current = start_date
        total_rows = 0
        windows_processed = 0

        logger.info(
            "backfill_started",
            feature_set=feature_set.name,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            window_hours=window_hours,
        )

        while current <= end_date:
            rows = await self._engine.compute_feature_set(
                feature_set, features, as_of=current
            )
            total_rows += rows
            windows_processed += 1
            current += window

            if windows_processed % 10 == 0:
                logger.info(
                    "backfill_progress",
                    feature_set=feature_set.name,
                    windows_processed=windows_processed,
                    current=current.isoformat(),
                    total_rows=total_rows,
                )

        logger.info(
            "backfill_complete",
            feature_set=feature_set.name,
            windows_processed=windows_processed,
            total_rows=total_rows,
        )
        return total_rows


async def backfill_days(
    engine: BatchComputeEngine,
    feature_set: FeatureSet,
    features: list[FeatureDefinition],
    days: int = 90,
) -> int:
    """Convenience function to backfill N days of history."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    job = BackfillJob(engine)
    return await job.run(feature_set, features, start, end)
