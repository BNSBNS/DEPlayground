"""Isolation Forest anomaly detector.

Unsupervised: learns the "normal" distribution from historical features
and flags any row that sits in a sparse region of feature space. Fast,
robust, and a standard first line of defense in market surveillance.

The detector implements the ``AnomalyDetector`` port so the rest of the
system never touches ``sklearn`` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pandas as pd
from sklearn.ensemble import IsolationForest

from src.common.logging_config import get_logger
from src.ml.domain.models import AnomalyScore

if TYPE_CHECKING:
    from datetime import datetime

    import numpy as np

logger = get_logger(__name__)


class IsolationForestDetector:
    """Wraps ``sklearn.ensemble.IsolationForest`` behind the port."""

    name: str = "isolation_forest"

    #: Features the detector scores on. Present in every ``FeatureFrame`` row.
    DEFAULT_FEATURES: ClassVar[list[str]] = [
        "vwap",
        "total_volume",
        "price_range",
        "lmp_congestion",
    ]

    def __init__(
        self,
        symbol: str = "UNKNOWN",
        contamination: float = 0.01,
        n_estimators: int = 200,
        random_state: int = 42,
        feature_columns: list[str] | None = None,
    ) -> None:
        self.symbol = symbol
        self._contamination = contamination
        self._feature_columns = feature_columns or list(self.DEFAULT_FEATURES)
        self._model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
        )
        self._fitted = False

    # ------------------------------------------------------------------
    # AnomalyDetector.fit
    # ------------------------------------------------------------------
    def fit(self, features: pd.DataFrame) -> None:
        x = self._select(features)
        self._model.fit(x)
        self._fitted = True
        logger.info(
            "isolation_forest_fitted",
            symbol=self.symbol,
            rows=len(x),
            features=self._feature_columns,
        )

    # ------------------------------------------------------------------
    # AnomalyDetector.score
    # ------------------------------------------------------------------
    def score(self, features: pd.DataFrame) -> list[AnomalyScore]:
        if not self._fitted:
            raise RuntimeError("IsolationForestDetector must be fit before score().")

        x = self._select(features)
        # ``decision_function`` returns the signed anomaly score — higher is more
        # normal. Flip the sign so "bigger number" consistently means "weirder".
        raw = -self._model.decision_function(x)
        labels = self._model.predict(x)  # -1 == anomaly, 1 == normal

        return [
            AnomalyScore(
                symbol=self.symbol,
                window_start=self._row_timestamp(features, i),
                score=float(raw[i]),
                is_anomaly=bool(labels[i] == -1),
                detector_name=self.name,
            )
            for i in range(len(x))
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _select(self, features: pd.DataFrame) -> np.ndarray:
        missing = [c for c in self._feature_columns if c not in features.columns]
        if missing:
            raise KeyError(f"IsolationForest missing feature columns: {missing}")
        return features[self._feature_columns].astype(float).to_numpy()

    @staticmethod
    def _row_timestamp(features: pd.DataFrame, i: int) -> datetime:
        if isinstance(features.index, pd.DatetimeIndex):
            return features.index[i].to_pydatetime()
        return pd.Timestamp.utcnow().to_pydatetime()
