"""Machine learning forecasting & analysis module for the energy trading platform.

Architecture (hexagonal / ports-and-adapters):

    domain/         - pure business models (Forecast, AnomalyScore, ModelMetadata) + Protocols
    features/       - feature engineering + SQL repository over trade_aggregates
    models/         - classical, gradient, deep-learning, and anomaly adapters
    pipeline/       - training, inference, evaluation, scheduling
    store/          - model artifact store + Postgres repositories
    api/            - FastAPI router mounted into the main API service

Five design patterns are used together:

    1. Protocol / Port    - ForecastModel contract in domain/ports.py
    2. Strategy           - interchangeable model implementations
    3. Template Method    - BaseNeuralForecaster + GRU/CNN/MLP children
    4. Adapter            - NeuralForecastAdapter bridges DataFrame and Tensor worlds
    5. Registry / Factory - ModelRegistry resolves names to classes
"""
