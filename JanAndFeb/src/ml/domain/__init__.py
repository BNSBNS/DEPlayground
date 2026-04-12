"""Domain layer: pure business models and Protocol contracts.

No ML libraries are imported here. This layer defines WHAT the system does,
not HOW it does it. Every model adapter, repository, and service in the
outer layers depends on the ports defined here, never the other way around.
"""

from src.ml.domain.models import (
    AnomalyScore,
    Forecast,
    ForecastBatch,
    ModelMetadata,
)
from src.ml.domain.ports import (
    AnomalyDetector,
    FeatureRepository,
    ForecastModel,
    ForecastRepository,
    ModelRegistryRepository,
    ModelStore,
)

__all__ = [
    "AnomalyDetector",
    "AnomalyScore",
    "FeatureRepository",
    "Forecast",
    "ForecastBatch",
    "ForecastModel",
    "ForecastRepository",
    "ModelMetadata",
    "ModelRegistryRepository",
    "ModelStore",
]
