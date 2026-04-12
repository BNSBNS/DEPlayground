"""SARIMAX forecaster — classical statistical baseline.

Wraps ``statsmodels.tsa.statespace.SARIMAX``. Univariate: fits on the target
series only, ignores exogenous features. Emits native confidence intervals
via ``get_forecast().conf_int()``, which is the main reason you still want a
classical baseline in the lineup even when you have gradient boosting and DL.

Implements the ``ForecastModel`` Protocol defined in ``src.ml.domain.ports``.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import joblib
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from src.common.logging_config import get_logger
from src.ml.domain.models import Forecast, ForecastBatch, ModelMetadata

if TYPE_CHECKING:
    from statsmodels.tsa.statespace.sarimax import SARIMAXResults

    from src.ml.domain.ports import ModelStore

logger = get_logger(__name__)


class SARIMAXForecaster:
    """Univariate SARIMAX wrapper implementing the ForecastModel Protocol."""

    name = "sarimax"

    def __init__(
        self,
        order: tuple[int, int, int] = (2, 1, 2),
        seasonal_order: tuple[int, int, int, int] = (1, 0, 1, 24),
        symbol: str = "UNKNOWN",
        version: str | None = None,
    ) -> None:
        self.order = order
        self.seasonal_order = seasonal_order
        self.symbol = symbol
        self.version = version or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._feature_hash: str = ""
        self._results: SARIMAXResults | None = None

    # ------------------------------------------------------------------
    # ForecastModel.fit
    # ------------------------------------------------------------------
    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series[float],
    ) -> ModelMetadata:
        logger.info("Fitting SARIMAX", order=self.order, seasonal_order=self.seasonal_order)

        # We carry the feature hash even though we don't use the feature columns,
        # so the lineage is still accurate.
        self._feature_hash = getattr(features, "attrs", {}).get("feature_hash", "")

        model = SARIMAX(
            target.astype(float),
            order=self.order,
            seasonal_order=self.seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        self._results = model.fit(disp=False)

        return ModelMetadata(
            model_name=self.name,
            model_version=self.version,
            trained_at=datetime.now(UTC),
            metrics={"aic": float(self._results.aic), "bic": float(self._results.bic)},
            params={
                "order": list(self.order),
                "seasonal_order": list(self.seasonal_order),
                "symbol": self.symbol,
            },
            artifact_uri="pending",  # overwritten by the trainer after save()
        )

    # ------------------------------------------------------------------
    # ForecastModel.predict
    # ------------------------------------------------------------------
    def predict(
        self,
        features: pd.DataFrame,
        horizon: int,
    ) -> ForecastBatch:
        if self._results is None:
            raise RuntimeError("SARIMAX model must be fit before predict().")

        forecast_result = self._results.get_forecast(steps=horizon)
        mean = forecast_result.predicted_mean
        ci = forecast_result.conf_int(alpha=0.2)  # 80% confidence band

        # Use the last index from features as the anchor for forecast_for timestamps.
        last_ts = self._last_timestamp(features)
        generated_at = datetime.now(UTC)

        forecasts: list[Forecast] = []
        for i in range(horizon):
            target_ts = last_ts + timedelta(minutes=i + 1)
            forecasts.append(
                Forecast(
                    symbol=self.symbol,
                    forecast_for=target_ts,
                    generated_at=generated_at,
                    horizon_minutes=i + 1,
                    yhat=Decimal(str(round(float(mean.iloc[i]), 8))),
                    yhat_lower=Decimal(str(round(float(ci.iloc[i, 0]), 8))),
                    yhat_upper=Decimal(str(round(float(ci.iloc[i, 1]), 8))),
                    model_name=self.name,
                    model_version=self.version,
                    feature_hash=self._feature_hash or "sarimax-univariate",
                )
            )

        return ForecastBatch(forecasts=forecasts)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, store: ModelStore) -> str:
        if self._results is None:
            raise RuntimeError("Cannot save an unfitted model.")

        buf = io.BytesIO()
        joblib.dump(self._results, buf)

        metadata: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "symbol": self.symbol,
            "order": list(self.order),
            "seasonal_order": list(self.seasonal_order),
            "feature_hash": self._feature_hash,
        }
        return store.save(self.name, self.version, buf.getvalue(), metadata)

    @classmethod
    def load(cls, store: ModelStore, uri: str) -> SARIMAXForecaster:
        artifact, metadata = store.load(uri)
        model = cls(
            order=tuple(metadata["order"]),
            seasonal_order=tuple(metadata["seasonal_order"]),
            symbol=metadata["symbol"],
            version=metadata["version"],
        )
        model._results = joblib.load(io.BytesIO(artifact))
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
