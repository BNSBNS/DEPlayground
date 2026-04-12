# ML Forecasting Module

The `src/ml/` package adds short-term VWAP forecasting and anomaly detection
on top of the existing trading platform. The core design goal is **learnability**:
every connecting part — from DB rows to features to tensors to API responses —
is written as small, explicit Python with no framework magic.

## Architecture at a glance

```
TimescaleDB (trade_aggregates)
        │
        ▼                                   ┌────────────────┐
SQLFeatureRepository  ──►  FeatureBuilder ──┤ FeatureFrame   │
                                            └──────┬─────────┘
                                                   │
                                        ┌──────────┴───────────┐
                                        │                      │
                                 TrainingPipeline      InferenceService
                                        │                      │
                              ModelRegistry.create()   model_loaders[name]
                                        │                      │
                      ┌─────────────────┼──────────────┐        │
                      ▼                 ▼              ▼        ▼
              SARIMAXForecaster  LightGBMForecaster  NeuralForecastAdapter
                                                            │
                                        ┌───────────────────┼───────────────────┐
                                        ▼                   ▼                   ▼
                                  MLPForecaster      GRUForecaster       CNNForecaster
                                        └──── all inherit ──┘
                                         BaseNeuralForecaster (Template Method)
```

## Five design patterns, one per file you'd expect

| Pattern | File | Purpose |
|---|---|---|
| Protocol / Port | `domain/ports.py` | Contract every forecaster satisfies |
| Strategy | `models/registry.py` + all adapters | Swap models at runtime by name |
| Template Method | `models/deep/base.py` | Share the full PyTorch training loop across children |
| Adapter | `models/deep/adapter.py` | Bridge DataFrame ↔ Tensor worlds |
| Registry / Factory | `models/registry.py` | Resolve `"gru"` → `GRUForecaster` |

## Module map

| Concern | Where |
|---|---|
| Database schema | `sql/schema/007_create_ml_tables.sql` |
| Domain (Pydantic + Protocols) | `src/ml/domain/` |
| Feature engineering | `src/ml/features/` |
| Classical forecaster (SARIMAX) | `src/ml/models/classical/arima.py` |
| Gradient forecaster (LightGBM, quantile CIs) | `src/ml/models/gradient/lightgbm_model.py` |
| Deep forecasters (MLP / GRU / CNN) | `src/ml/models/deep/` |
| Anomaly detectors (IsolationForest + residual) | `src/ml/models/anomaly/` |
| Training & inference pipelines | `src/ml/pipeline/` |
| Filesystem model store + Postgres repos | `src/ml/store/` |
| REST/API router | `src/ml/api/routes.py` (mounted at `/api/v1`) |
| Bootstrap (model registration + loaders) | `src/ml/bootstrap.py` |
| CLI (`trade-ml`) | `src/ml/main.py` |
| Cron retraining | `src/ml/pipeline/scheduler.py` |

## Container topology

The ML stack is split into dedicated containers so the core trading path
stays lean. Three images are involved:

| Container | Base image | Carries torch/lightgbm? | Role |
|---|---|---|---|
| `api` | `docker/api/Dockerfile` | **No** | Read-only REST endpoints over `forecasts` / `anomaly_scores` / `model_registry` |
| `ml-scheduler` | `docker/ml/Dockerfile` | **Yes** | Long-running APScheduler cron that retrains and writes back to Postgres |
| `ml-trainer` | `docker/ml/Dockerfile` | **Yes** | One-shot `trade-ml train …` runs |

The ML containers are gated behind the `ml` compose profile so running
`docker compose up` without `--profile ml` leaves the forecasting stack
dormant.

```bash
# Apply schema (once)
docker compose -f JanAndFeb/docker-compose.yml up -d postgres
docker compose -f JanAndFeb/docker-compose.yml exec -T postgres \
    psql -U trading -d trades < JanAndFeb/sql/schema/007_create_ml_tables.sql

# Build the ML image
docker compose -f JanAndFeb/docker-compose.yml --profile ml build ml-scheduler

# Run a one-shot training job for each strategy
docker compose -f JanAndFeb/docker-compose.yml --profile ml run --rm ml-trainer \
    trade-ml train --model sarimax  --symbol POWER_DE
docker compose -f JanAndFeb/docker-compose.yml --profile ml run --rm ml-trainer \
    trade-ml train --model lightgbm --symbol POWER_DE
docker compose -f JanAndFeb/docker-compose.yml --profile ml run --rm ml-trainer \
    trade-ml train --model gru      --symbol POWER_DE

# Bring up the long-running retrain scheduler
docker compose -f JanAndFeb/docker-compose.yml --profile ml up -d ml-scheduler

# Read from the lean API container
curl "http://localhost:8000/api/v1/forecasts/POWER_DE?model=lightgbm&horizon=15"
curl "http://localhost:8000/api/v1/anomalies/POWER_DE?hours=6"
curl "http://localhost:8000/api/v1/models"
```

The `/api/v1/forecasts/{symbol}` endpoint is a **pure read path** — it
queries the `forecasts` hypertable. Fresh inference is performed
out-of-band by the `ml-scheduler` container, which writes its predictions
back to the same hypertable.

### Local dev without Docker

If you prefer running the worker locally against a dockerised Postgres:

```bash
conda env update -f JanAndFeb/environment.yml
conda activate energy-trading
pip install -e ".[dev,ml]"

docker compose -f JanAndFeb/docker-compose.yml up -d postgres
trade-ml train --model lightgbm --symbol POWER_DE
trade-ml schedule
```

## Visualisation

`monitoring/grafana/provisioning/dashboards/forecasts.json` provides an
**Actual VWAP vs Forecast** overlay, rolling MAE per model, model freshness
stat, anomaly table, and a model-version lineage table sourced from
`model_registry`. Grafana picks it up automatically via the existing
provisioning config.

## Quality gates

Run locally against a conda env with the `[dev,ml]` extras installed:

```bash
ruff check JanAndFeb/src/ml/ JanAndFeb/tests/unit/ml/
ruff format --check JanAndFeb/src/ml/ JanAndFeb/tests/unit/ml/
mypy JanAndFeb/src/ml/ --strict
pytest JanAndFeb/tests/unit/ml -v --cov=src/ml --cov-report=term-missing
```

Or inside the ML container — useful when your local env is missing
torch/lightgbm/statsmodels:

```bash
docker compose -f JanAndFeb/docker-compose.yml --profile ml run --rm \
    --entrypoint bash ml-trainer -lc "\
      pip install '.[dev]' && \
      ruff check src/ml tests/unit/ml && \
      ruff format --check src/ml tests/unit/ml && \
      mypy src/ml --strict && \
      pytest tests/unit/ml -v"
```
