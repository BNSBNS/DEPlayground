"""Ports (Protocols) for the forecasting module.

These define the contracts that adapters must implement. The trainer, the
inference service, and the API all depend only on these Protocols — never on
concrete ML libraries. This is the seam that lets us swap statsmodels for
MLflow, LightGBM for XGBoost, or filesystem storage for S3 without touching
the pipeline code.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd

    from src.ml.domain.models import (
        AnomalyScore,
        ForecastBatch,
        ModelMetadata,
    )


@runtime_checkable
class ModelStore(Protocol):
    """Stores model artifacts (the fitted weights / state) and their metadata.

    Implementations: ``FilesystemModelStore`` (local disk). Future: S3, MLflow.
    """

    def save(
        self,
        name: str,
        version: str,
        artifact: bytes,
        metadata: dict[str, Any],
    ) -> str:
        """Persist an artifact and return a URI that ``load`` can resolve."""

    def load(self, uri: str) -> tuple[bytes, dict[str, Any]]:
        """Return ``(artifact_bytes, metadata)`` for the given URI."""

    def exists(self, uri: str) -> bool:
        """Return True if an artifact exists at ``uri``."""


@runtime_checkable
class ForecastModel(Protocol):
    """Every forecaster — classical, gradient, or deep — implements this.

    The contract is intentionally narrow: fit on a DataFrame, predict over a
    horizon, persist, and reload. Model-family specifics (hyperparameters,
    training loops, quantile heads) stay hidden inside the adapter.
    """

    name: str
    version: str

    def fit(
        self,
        features: "pd.DataFrame",
        target: "pd.Series[float]",
    ) -> "ModelMetadata":
        """Fit the model and return metadata describing the training run."""

    def predict(
        self,
        features: "pd.DataFrame",
        horizon: int,
    ) -> "ForecastBatch":
        """Produce a ``ForecastBatch`` covering ``horizon`` future steps."""

    def save(self, store: ModelStore) -> str:
        """Persist this model via ``store`` and return the artifact URI."""


@runtime_checkable
class AnomalyDetector(Protocol):
    """Protocol for anomaly detectors (unsupervised or residual-based)."""

    name: str

    def fit(self, features: "pd.DataFrame") -> None:
        """Learn the normal distribution from training data."""

    def score(self, features: "pd.DataFrame") -> list["AnomalyScore"]:
        """Return one ``AnomalyScore`` per row in ``features``."""


@runtime_checkable
class FeatureRepository(Protocol):
    """Reads raw history from the trade_aggregates table (or any source)."""

    def load_history(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> "pd.DataFrame":
        """Return a DataFrame indexed by ``window_start`` (UTC)."""


@runtime_checkable
class ForecastRepository(Protocol):
    """Persists ``ForecastBatch`` objects and reads them back for the API."""

    def save(self, batch: "ForecastBatch") -> None: ...

    def load_latest(
        self,
        symbol: str,
        model_name: str,
        limit: int = 100,
    ) -> "ForecastBatch": ...


@runtime_checkable
class ModelRegistryRepository(Protocol):
    """Persists ``ModelMetadata`` for lineage tracking."""

    def save(self, metadata: "ModelMetadata") -> None: ...

    def load_latest(self, model_name: str) -> "ModelMetadata | None": ...

    def list_all(self) -> list["ModelMetadata"]: ...
