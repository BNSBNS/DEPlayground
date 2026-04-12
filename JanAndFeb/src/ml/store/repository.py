"""Postgres repositories for forecasts and model registry.

Both repositories reuse the existing ``DatabaseWriter`` connection pool so
the ML layer shares the same pool settings and metrics as the trading hot
path. All writes are idempotent (``ON CONFLICT DO UPDATE``) so retries and
reprocessing are safe.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.common.logging_config import get_logger
from src.ml.domain.models import (
    Forecast,
    ForecastBatch,
    ModelMetadata,
)

if TYPE_CHECKING:
    from src.consumer.db_writer import DatabaseWriter

logger = get_logger(__name__)

# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------
_UPSERT_FORECAST_SQL = """
    INSERT INTO forecasts (
        symbol, forecast_for, generated_at, horizon_minutes,
        yhat, yhat_lower, yhat_upper,
        model_name, model_version, feature_hash
    ) VALUES (
        %(symbol)s, %(forecast_for)s, %(generated_at)s, %(horizon_minutes)s,
        %(yhat)s, %(yhat_lower)s, %(yhat_upper)s,
        %(model_name)s, %(model_version)s, %(feature_hash)s
    )
    ON CONFLICT (symbol, forecast_for, model_name, model_version) DO UPDATE SET
        generated_at    = EXCLUDED.generated_at,
        horizon_minutes = EXCLUDED.horizon_minutes,
        yhat            = EXCLUDED.yhat,
        yhat_lower      = EXCLUDED.yhat_lower,
        yhat_upper      = EXCLUDED.yhat_upper,
        feature_hash    = EXCLUDED.feature_hash
"""

_SELECT_LATEST_FORECASTS_SQL = """
    SELECT symbol, forecast_for, generated_at, horizon_minutes,
           yhat, yhat_lower, yhat_upper,
           model_name, model_version, feature_hash
    FROM forecasts
    WHERE symbol = %(symbol)s
      AND model_name = %(model_name)s
    ORDER BY forecast_for DESC
    LIMIT %(limit)s
"""

_UPSERT_REGISTRY_SQL = """
    INSERT INTO model_registry (
        model_name, model_version, trained_at, metrics, params, artifact_uri
    ) VALUES (
        %(model_name)s, %(model_version)s, %(trained_at)s,
        %(metrics)s, %(params)s, %(artifact_uri)s
    )
    ON CONFLICT (model_name, model_version) DO UPDATE SET
        trained_at   = EXCLUDED.trained_at,
        metrics      = EXCLUDED.metrics,
        params       = EXCLUDED.params,
        artifact_uri = EXCLUDED.artifact_uri
"""

_SELECT_LATEST_REGISTRY_SQL = """
    SELECT model_name, model_version, trained_at, metrics, params, artifact_uri
    FROM model_registry
    WHERE model_name = %(model_name)s
    ORDER BY trained_at DESC
    LIMIT 1
"""

_SELECT_ALL_REGISTRY_SQL = """
    SELECT model_name, model_version, trained_at, metrics, params, artifact_uri
    FROM model_registry
    ORDER BY trained_at DESC
"""


class PostgresForecastRepository:
    """Persists ``ForecastBatch`` to the ``forecasts`` hypertable."""

    def __init__(self, db_writer: DatabaseWriter) -> None:
        self._db = db_writer

    def save(self, batch: ForecastBatch) -> None:
        if not batch.forecasts:
            return

        rows = [
            {
                "symbol": f.symbol,
                "forecast_for": f.forecast_for,
                "generated_at": f.generated_at,
                "horizon_minutes": f.horizon_minutes,
                "yhat": f.yhat,
                "yhat_lower": f.yhat_lower,
                "yhat_upper": f.yhat_upper,
                "model_name": f.model_name,
                "model_version": f.model_version,
                "feature_hash": f.feature_hash,
            }
            for f in batch.forecasts
        ]

        with self._db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(_UPSERT_FORECAST_SQL, rows)
            conn.commit()

        logger.info("Saved forecast batch", count=len(rows))

    def load_latest(
        self,
        symbol: str,
        model_name: str,
        limit: int = 100,
    ) -> ForecastBatch:
        params = {"symbol": symbol, "model_name": model_name, "limit": limit}
        with self._db._get_connection() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_LATEST_FORECASTS_SQL, params)
            rows = cur.fetchall()

        forecasts = [Forecast.model_validate(dict(row)) for row in rows]
        return ForecastBatch(forecasts=forecasts)


class PostgresModelRegistryRepository:
    """Persists and reads ``ModelMetadata`` from the ``model_registry`` table."""

    def __init__(self, db_writer: DatabaseWriter) -> None:
        self._db = db_writer

    def save(self, metadata: ModelMetadata) -> None:
        params = {
            "model_name": metadata.model_name,
            "model_version": metadata.model_version,
            "trained_at": metadata.trained_at,
            "metrics": json.dumps(metadata.metrics),
            "params": json.dumps(metadata.params, default=str),
            "artifact_uri": metadata.artifact_uri,
        }
        with self._db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_UPSERT_REGISTRY_SQL, params)
            conn.commit()

        logger.info(
            "Registered model",
            name=metadata.model_name,
            version=metadata.model_version,
            metrics=metadata.metrics,
        )

    def load_latest(self, model_name: str) -> ModelMetadata | None:
        with self._db._get_connection() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_LATEST_REGISTRY_SQL, {"model_name": model_name})
            row = cur.fetchone()
        return self._row_to_metadata(dict(row)) if row else None

    def list_all(self) -> list[ModelMetadata]:
        with self._db._get_connection() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_ALL_REGISTRY_SQL)
            rows = cur.fetchall()
        return [self._row_to_metadata(dict(r)) for r in rows]

    @staticmethod
    def _row_to_metadata(row: dict[str, object]) -> ModelMetadata:
        return ModelMetadata.model_validate(
            {
                "model_name": row["model_name"],
                "model_version": row["model_version"],
                "trained_at": row["trained_at"],
                "metrics": (
                    json.loads(str(row["metrics"]))
                    if isinstance(row["metrics"], str)
                    else row["metrics"]
                ),
                "params": (
                    json.loads(str(row["params"]))
                    if isinstance(row["params"], str)
                    else row["params"]
                ),
                "artifact_uri": row["artifact_uri"],
            }
        )
