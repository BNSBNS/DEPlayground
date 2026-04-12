"""Deep-learning forecasters.

Three architectural paradigms share a single ``BaseNeuralForecaster`` via
the Template Method pattern:

* ``MLPForecaster``  - fully connected baseline (flattened sequence)
* ``GRUForecaster``  - recurrent (reads sequence step-by-step)
* ``CNNForecaster``  - 1D dilated convolutions over time (parallel, local)

A single ``NeuralForecastAdapter`` wraps any of the three to satisfy the
``ForecastModel`` port — that's where DataFrame/Tensor translation happens.
"""

from src.ml.models.deep.adapter import NeuralForecastAdapter
from src.ml.models.deep.base import BaseNeuralForecaster
from src.ml.models.deep.cnn import CNNForecaster
from src.ml.models.deep.gru import GRUForecaster
from src.ml.models.deep.mlp import MLPForecaster

__all__ = [
    "BaseNeuralForecaster",
    "CNNForecaster",
    "GRUForecaster",
    "MLPForecaster",
    "NeuralForecastAdapter",
]
