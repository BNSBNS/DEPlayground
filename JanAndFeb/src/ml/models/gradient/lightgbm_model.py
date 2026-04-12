"""LightGBM quantile forecaster — gradient boosting strategy.

Fits three separate LightGBM models for the 10%, 50%, and 90% quantiles so
forecasts carry native confidence bands. This is the standard production
recipe for gradient-boosted quantile forecasting (used e.g. in the M5
competition winners and most commercial energy-load forecasters).

Recursive prediction: at inference time we predict one step ahead, shift the
lag features, and repeat until the requested horizon is reached. Simple,
clear, and keeps the feature engineering identical between train and serve.

Implements the ``ForecastModel`` Protocol.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import joblib
import lightgbm as lgb
import pandas as pd

from src.common.logging_config import get_logger
from src.ml.domain.models import Forecast, ForecastBatch, ModelMetadata

if TYPE_CHECKING:
    from src.ml.domain.ports import ModelStore

logger = get_logger(__name__)

_QUANTILES = {"lower": 0.10, "median": 0.50, "upper": 0.90}


class LightGBMForecaster:
    """LightGBM quantile regressor implementing the ForecastModel Protocol."""

    name = "lightgbm"

    def __init__(
        self,
        symbol: str = "UNKNOWN",
        version: str | None = None,
        num_leaves: int = 31,
        learning_rate: float = 0.05,
        n_estimators: int = 200,
        min_child_samples: int = 20,
    ) -> None:
        self.symbol = symbol
        self.version = version or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._params: dict[str, Any] = {
            "objective": "quantile",
            "num_leaves": num_leaves,
            "learning_rate": learning_rate,
            "n_estimators": n_estimators,
            "min_child_samples": min_child_samples,
            "verbosity": -1,
        }
        self._models: dict[str, lgb.LGBMRegressor] = {}
        self._feature_columns: list[str] = []
        self._feature_hash: str = ""

    # ------------------------------------------------------------------
    # ForecastModel.fit
    # ------------------------------------------------------------------
    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series[float],
    ) -> ModelMetadata:
        logger.info("Fitting LightGBM quantile ensemble", n=len(features))

        self._feature_columns = list(features.columns)
        self._feature_hash = getattr(features, "attrs", {}).get("feature_hash", "")

        x = features.values
        y = target.astype(float).values

        metrics: dict[str, float] = {}
        for label, q in _QUANTILES.items():
            model = lgb.LGBMRegressor(**self._params, alpha=q)
            model.fit(x, y)
            self._models[label] = model
            # Training MAE — only a sanity check, not a validation metric.
            if label == "median":
                preds = model.predict(x)
                metrics["train_mae"] = float((abs(preds - y)).mean())

        return ModelMetadata(
            model_name=self.name,
            model_version=self.version,
            trained_at=datetime.now(UTC),
            metrics=metrics,
            params={**self._params, "symbol": self.symbol},
            artifact_uri="pending",
        )

    # ------------------------------------------------------------------
    # ForecastModel.predict
    # ------------------------------------------------------------------
    def predict(
        self,
        features: pd.DataFrame,
        horizon: int,
    ) -> ForecastBatch:
        if not self._models:
            raise RuntimeError("LightGBM model must be fit before predict().")

        # Start from the most recent row; advance by copying the row and
        # updating its vwap_lag_1 / rolling features the cheap way.
        last_row = features.iloc[[-1]][self._feature_columns].copy()
        last_ts = self._last_timestamp(features)
        generated_at = datetime.now(UTC)

        forecasts: list[Forecast] = []
        prev_yhat: float | None = None

        for step in range(1, horizon + 1):
            if prev_yhat is not None and "vwap_lag_1" in last_row.columns:
                last_row["vwap_lag_1"] = prev_yhat

            x = last_row.values
            yhat = float(self._models["median"].predict(x)[0])
            y_lo = float(self._models["lower"].predict(x)[0])
            y_hi = float(self._models["upper"].predict(x)[0])

            forecasts.append(
                Forecast(
                    symbol=self.symbol,
                    forecast_for=last_ts + timedelta(minutes=step),
                    generated_at=generated_at,
                    horizon_minutes=step,
                    yhat=Decimal(str(round(yhat, 8))),
                    yhat_lower=Decimal(str(round(y_lo, 8))),
                    yhat_upper=Decimal(str(round(y_hi, 8))),
                    model_name=self.name,
                    model_version=self.version,
                    feature_hash=self._feature_hash or "lightgbm-features",
                )
            )
            prev_yhat = yhat

        return ForecastBatch(forecasts=forecasts)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, store: ModelStore) -> str:
        if not self._models:
            raise RuntimeError("Cannot save an unfitted model.")

        buf = io.BytesIO()
        joblib.dump(
            {
                "models": self._models,
                "feature_columns": self._feature_columns,
            },
            buf,
        )
        metadata: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "symbol": self.symbol,
            "params": self._params,
            "feature_hash": self._feature_hash,
            "feature_columns": self._feature_columns,
        }
        return store.save(self.name, self.version, buf.getvalue(), metadata)

    @classmethod
    def load(cls, store: ModelStore, uri: str) -> LightGBMForecaster:
        artifact, metadata = store.load(uri)
        model = cls(symbol=metadata["symbol"], version=metadata["version"])
        payload = joblib.load(io.BytesIO(artifact))
        model._models = payload["models"]
        model._feature_columns = payload["feature_columns"]
        model._feature_hash = metadata.get("feature_hash", "")
        return model

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _last_timestamp(features: pd.DataFrame) -> datetime:
        if isinstance(features.index, pd.DatetimeIndex) and len(features.index):
            ts = features.index[-1]
            return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        return datetime.now(UTC)
