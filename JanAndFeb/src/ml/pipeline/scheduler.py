"""Periodic retraining scheduler.

Uses APScheduler's BlockingScheduler in CLI mode and BackgroundScheduler
when embedded. A single cron expression (from ``MLSettings.retrain_cron``)
fires ``TrainingPipeline.run`` for every configured (model, symbol) pair.
After every successful run the ``InferenceService`` cache is invalidated
so the new version is picked up on the next request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.common.logging_config import get_logger

if TYPE_CHECKING:
    from src.ml.config import MLSettings
    from src.ml.pipeline.inference import InferenceService
    from src.ml.pipeline.trainer import TrainingPipeline

logger = get_logger(__name__)


class RetrainScheduler:
    """Wraps APScheduler with sensible defaults for our retrain job."""

    def __init__(
        self,
        settings: MLSettings,
        trainer: TrainingPipeline,
        inference: InferenceService | None = None,
        *,
        blocking: bool = True,
    ) -> None:
        self._settings = settings
        self._trainer = trainer
        self._inference = inference
        self._scheduler: BlockingScheduler | BackgroundScheduler = (
            BlockingScheduler() if blocking else BackgroundScheduler()
        )

    def start(self) -> None:
        trigger = CronTrigger.from_crontab(self._settings.retrain_cron)
        self._scheduler.add_job(
            self._run_once,
            trigger=trigger,
            id="ml_retrain",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "retrain_scheduler_started",
            cron=self._settings.retrain_cron,
            symbols=self._settings.symbols,
            model=self._settings.model_name,
        )
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    # ------------------------------------------------------------------
    def _run_once(self) -> None:
        """Train the configured model for every configured symbol."""
        for symbol in self._settings.symbols:
            try:
                self._trainer.run(
                    model_name=self._settings.model_name,
                    symbol=symbol,
                )
            except Exception:
                logger.exception("retrain_failed", symbol=symbol, model=self._settings.model_name)
                continue

        if self._inference is not None:
            self._inference.invalidate_cache()
            logger.info("inference_cache_invalidated")
