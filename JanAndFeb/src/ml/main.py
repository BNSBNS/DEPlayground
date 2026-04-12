"""``trade-ml`` CLI — one entry point, two subcommands.

Usage::

    trade-ml train    --model gru --symbol POWER_DE
    trade-ml schedule

Training runs end-to-end through ``TrainingPipeline`` and exits.
Schedule mode starts APScheduler and blocks forever.
"""

from __future__ import annotations

import argparse
import sys

from src.common.config import get_settings
from src.common.logging_config import configure_logging, get_logger
from src.consumer.db_writer import DatabaseWriter
from src.ml.bootstrap import MODEL_LOADERS, register_models
from src.ml.config import get_ml_settings
from src.ml.features.builder import FeatureBuilder
from src.ml.features.repository import SQLFeatureRepository
from src.ml.models.registry import registry
from src.ml.pipeline.inference import InferenceService
from src.ml.pipeline.scheduler import RetrainScheduler
from src.ml.pipeline.trainer import TrainingPipeline
from src.ml.store.filesystem import FilesystemModelStore
from src.ml.store.repository import (
    PostgresForecastRepository,
    PostgresModelRegistryRepository,
)

logger = get_logger(__name__)


def _build_context() -> tuple[TrainingPipeline, InferenceService]:
    """Wire every dependency once — used by both subcommands."""
    configure_logging()
    register_models()

    ml_settings = get_ml_settings()
    base_settings = get_settings()

    db_writer = DatabaseWriter(base_settings.postgres)

    feature_repo = SQLFeatureRepository(db_writer)
    forecast_repo = PostgresForecastRepository(db_writer)
    registry_repo = PostgresModelRegistryRepository(db_writer)
    model_store = FilesystemModelStore(ml_settings.model_store_path)
    feature_builder = FeatureBuilder()

    trainer = TrainingPipeline(
        feature_repo=feature_repo,
        model_store=model_store,
        registry_repo=registry_repo,
        model_registry=registry,
        feature_builder=feature_builder,
        train_history_days=ml_settings.train_history_days,
        eval_folds=ml_settings.eval_folds,
        min_train_rows=ml_settings.min_train_rows,
        horizon=ml_settings.horizon_minutes,
    )

    inference = InferenceService(
        feature_repo=feature_repo,
        forecast_repo=forecast_repo,
        registry_repo=registry_repo,
        model_store=model_store,
        feature_builder=feature_builder,
        model_loaders=MODEL_LOADERS,
        infer_history_minutes=ml_settings.infer_history_minutes,
    )

    return trainer, inference


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def _cmd_train(args: argparse.Namespace) -> int:
    trainer, _ = _build_context()
    ml_settings = get_ml_settings()

    hparams: dict[str, object] = {
        "hidden_size": ml_settings.hidden_size,
        "num_layers": ml_settings.num_layers,
        "dropout": ml_settings.dropout,
        "seq_len": ml_settings.seq_len,
        "horizon": ml_settings.horizon_minutes,
        "epochs": ml_settings.epochs,
        "batch_size": ml_settings.batch_size,
        "learning_rate": ml_settings.learning_rate,
        "patience": ml_settings.early_stopping_patience,
    }

    meta = trainer.run(model_name=args.model, symbol=args.symbol, hparams=hparams)
    logger.info(
        "train_command_done",
        model=meta.model_name,
        version=meta.model_version,
        metrics=meta.metrics,
        artifact_uri=meta.artifact_uri,
    )
    return 0


def _cmd_schedule(args: argparse.Namespace) -> int:  # noqa: ARG001
    trainer, inference = _build_context()
    scheduler = RetrainScheduler(
        settings=get_ml_settings(),
        trainer=trainer,
        inference=inference,
        blocking=True,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("scheduler_stopped")
    return 0


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trade-ml", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train", help="Train one model for one symbol and exit.")
    train.add_argument("--model", required=True, help="Model name (sarimax/lightgbm/mlp/gru/cnn).")
    train.add_argument("--symbol", required=True, help="Symbol to train on (e.g. POWER_DE).")
    train.set_defaults(func=_cmd_train)

    schedule = sub.add_parser("schedule", help="Run the cron retrain loop forever.")
    schedule.set_defaults(func=_cmd_schedule)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
