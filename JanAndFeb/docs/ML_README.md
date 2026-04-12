# ML Forecasting & Anomaly Detection Module

A complete AI/ML forecasting and anomaly detection system for energy VWAP prices, built as a learning-first extension of the JanAndFeb energy trading platform. Every connecting part -- from database rows to engineered features to tensor operations to REST responses -- is written as explicit, readable Python with no framework magic.

---

## Table of Contents

1. [Why This Exists](#why-this-exists)
2. [C4 Architecture](#c4-architecture)
3. [Design Patterns & Rationale](#design-patterns--rationale)
4. [Model Families](#model-families)
5. [Feature Engineering](#feature-engineering)
6. [Anomaly Detection](#anomaly-detection)
7. [Training Pipeline](#training-pipeline)
8. [Evaluation Strategy](#evaluation-strategy)
9. [Data Contracts](#data-contracts)
10. [Database Schema](#database-schema)
11. [Container Topology](#container-topology)
12. [API Reference](#api-reference)
13. [Configuration](#configuration)
14. [Usage](#usage)
15. [Taking It Apart](#taking-it-apart)
16. [Quality Gates](#quality-gates)
17. [File Map](#file-map)
18. [Design Decisions & Trade-offs](#design-decisions--trade-offs)

---

## Why This Exists

The energy trading platform already handles real-time ingestion (Kafka), windowed VWAP aggregation, and TimescaleDB storage. What it lacked was any predictive capability: no short-term price forecasts, no anomaly detection, no model lifecycle management.

This module adds all three, using the same hexagonal architecture principles as the rest of the platform. The primary goal is **learning**: understanding how data flows from a database table through feature engineering, into model training, through persistence and versioning, out through an API, and onto a dashboard -- with every type transition visible and every design decision explicit.

The secondary goal is **production shape**: the architecture is intentionally shaped like what you would find in a real energy forecasting desk (TimescaleDB + model registry + REST API + Grafana drift dashboards), so it could evolve into a production system without rewriting.

---

## C4 Architecture

### Level 1: System Context

```
                         Energy Trading Platform
                         =======================
                                  |
    ┌─────────────────────────────┼──────────────────────────────┐
    |                             |                              |
    |  Kafka + Consumer           |  ML Module (NEW)             |  REST API
    |  ─────────────────          |  ────────────────            |  ────────
    |  Real-time trades    ──────>|  Forecasting                 |  /api/v1/forecasts
    |  1-min VWAP aggs     ──────>|  Anomaly detection    ──────>|  /api/v1/anomalies
    |  trade_aggregates    ──────>|  Model registry              |  /api/v1/models
    |                             |                              |
    └─────────────────────────────┼──────────────────────────────┘
                                  |
                           TimescaleDB
                     (trade_aggregates, forecasts,
                      anomaly_scores, model_registry)
```

The ML module is a **read-only consumer** of `trade_aggregates` and a **writer** to three new tables: `forecasts`, `anomaly_scores`, and `model_registry`. It never touches the Kafka consumer, the aggregator, or the existing trading hot path.

### Level 2: Container Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
|                            Docker Compose                                |
|                                                                          |
|  ALWAYS-ON (no profile needed)                                           |
|  ┌───────────────────┐  ┌───────────────────────────────────────────┐   |
|  | postgres           |  | api                                       |   |
|  | (TimescaleDB)      |  | (FastAPI -- lean, NO torch/lgb/stats)     |   |
|  | - trade_aggregates |  | - GET /api/v1/forecasts/{symbol}          |   |
|  | - forecasts        |  | - GET /api/v1/anomalies/{symbol}          |   |
|  | - anomaly_scores   |  | - GET /api/v1/models                     |   |
|  | - model_registry   |  |   (pure reads from DB)                    |   |
|  └───────────────────┘  └───────────────────────────────────────────┘   |
|                                                                          |
|  PROFILE: ml  (docker-compose --profile ml)                              |
|  ┌───────────────────────────────────────────────────────────────────┐   |
|  | ml-scheduler                                                       |   |
|  | (Full ML stack: torch + lightgbm + statsmodels + sklearn)          |   |
|  | - APScheduler cron loop (default: daily 02:00 UTC)                 |   |
|  | - For each symbol x model: train -> persist -> write forecasts     |   |
|  └───────────────────────────────────────────────────────────────────┘   |
|  ┌───────────────────────────────────────────────────────────────────┐   |
|  | ml-trainer                                                         |   |
|  | (Same image as ml-scheduler)                                       |   |
|  | - One-shot: trade-ml train --model gru --symbol POWER_DE           |   |
|  └───────────────────────────────────────────────────────────────────┘   |
└──────────────────────────────────────────────────────────────────────────┘
```

**Key insight**: the API container is intentionally **lean** -- it has zero ML dependencies. It reads pre-computed forecasts from the `forecasts` hypertable. Fresh inference happens out-of-band in the `ml-scheduler` container, which writes predictions back to the same table. This separation means the API can cold-start in < 2 seconds and doesn't need 2GB+ of PyTorch/CUDA wheels.

### Level 3: Component Diagram (src/ml/)

```
┌─────────────────────────────────────────────────────────────────────────┐
|  src/ml/                                                                 |
|                                                                          |
|  ┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐    |
|  | domain/      |     | features/         |     | store/             |    |
|  | - models.py  |     | - schema.py       |     | - filesystem.py    |    |
|  |   (Forecast, |     |   (FeatureFrame)  |     |   (ModelStore)     |    |
|  |    Anomaly,  |     | - builder.py      |     | - repository.py    |    |
|  |    Metadata) |     |   (FeatureBuilder)|     |   (Postgres repos) |    |
|  | - ports.py   |     | - repository.py   |     └───────────────────┘    |
|  |   (Protocols)|     |   (SQL reader)    |                              |
|  └──────┬──────┘     └────────┬─────────┘                              |
|         |                     |                                          |
|         |     ┌───────────────┴───────────────────────────────┐         |
|         |     |                                               |         |
|         ▼     ▼                                               ▼         |
|  ┌──────────────────────────────────────────────────────────────────┐   |
|  | models/                                                          |   |
|  |                                                                  |   |
|  |  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  |   |
|  |  | classical/   |  | gradient/     |  | deep/                  |  |   |
|  |  | - arima.py   |  | - lightgbm_  |  | - base.py  (Template)  |  |   |
|  |  |  (SARIMAX)   |  |   model.py   |  | - adapter.py (Adapter) |  |   |
|  |  └──────────────┘  └──────────────┘  | - datasets.py          |  |   |
|  |                                       | - gru.py               |  |   |
|  |  ┌─────────────────────────────────┐ | - cnn.py               |  |   |
|  |  | anomaly/                         | | - mlp.py               |  |   |
|  |  | - iforest.py (IsolationForest)   | └────────────────────────┘  |   |
|  |  | - residual.py (Residual-based)   |                             |   |
|  |  └─────────────────────────────────┘                             |   |
|  |                                                                  |   |
|  |  registry.py  --  name -> factory resolution                     |   |
|  └──────────────────────────────────────────────────────────────────┘   |
|         |                                                                |
|         ▼                                                                |
|  ┌──────────────────────────────────────────────────────────────────┐   |
|  | pipeline/                                                        |   |
|  | - trainer.py      (train end-to-end, walk-forward eval, persist) |   |
|  | - inference.py    (load model, predict, write to forecasts)      |   |
|  | - evaluation.py   (MAE, RMSE, MAPE, sMAPE, pinball, WF splitter)|   |
|  | - scheduler.py    (APScheduler cron loop)                        |   |
|  └──────────────────────────────────────────────────────────────────┘   |
|         |                                                                |
|         ▼                                                                |
|  ┌──────────────────────┐    ┌────────────────┐    ┌────────────────┐   |
|  | api/routes.py         |    | bootstrap.py    |    | main.py        |   |
|  | (FastAPI router)      |    | (wiring + DI)   |    | (CLI entry)    |   |
|  └──────────────────────┘    └────────────────┘    └────────────────┘   |
└─────────────────────────────────────────────────────────────────────────┘
```

### Level 4: Class Hierarchy

```
ForecastModel (Protocol)                       -- domain/ports.py
        ^
        | implements
        |
        |-- SARIMAXForecaster                  -- models/classical/arima.py
        |-- LightGBMForecaster                 -- models/gradient/lightgbm_model.py
        '-- NeuralForecastAdapter              -- models/deep/adapter.py
                | wraps (has-a)
                v
        BaseNeuralForecaster (ABC, nn.Module)  -- models/deep/base.py  [Template Method]
                ^
                |-- GRUForecaster              -- models/deep/gru.py
                |-- CNNForecaster              -- models/deep/cnn.py
                '-- MLPForecaster              -- models/deep/mlp.py


AnomalyDetector (Protocol)                     -- domain/ports.py
        ^
        |-- IsolationForestDetector            -- models/anomaly/iforest.py
        '-- ResidualAnomalyDetector            -- models/anomaly/residual.py
                | composes (has-a) a Baseline callable
```

---

## Design Patterns & Rationale

Five patterns work together. Each has a single responsibility and a clear reason for existing.

### 1. Protocol / Port (Hexagonal Architecture)

**Where**: `domain/ports.py`

**What it does**: Defines `ForecastModel`, `AnomalyDetector`, `ModelStore`, `FeatureRepository`, `ForecastRepository`, and `ModelRegistryRepository` as Python `Protocol` classes. Every other file in the module depends only on these abstract contracts -- never on statsmodels, LightGBM, or PyTorch directly.

**Why**: This is the seam that lets you swap implementations. Replace `FilesystemModelStore` with S3 or MLflow? Change one file. Replace LightGBM with XGBoost? Add one file. The trainer, inference service, and API never know the difference.

**Industry context**: This is the hexagonal (ports & adapters) pattern documented by Alistair Cockburn and standard in production ML systems where the model library and serving infrastructure evolve independently.

```python
# domain/ports.py -- the entire system programs against this
@runtime_checkable
class ForecastModel(Protocol):
    name: str
    version: str
    def fit(self, features: pd.DataFrame, target: pd.Series[float]) -> ModelMetadata: ...
    def predict(self, features: pd.DataFrame, horizon: int) -> ForecastBatch: ...
    def save(self, store: ModelStore) -> str: ...
```

### 2. Strategy Pattern

**Where**: `models/registry.py` + all model implementations

**What it does**: The `ModelRegistry` maps string names to factory callables. The trainer asks for `"lightgbm"` and gets a `LightGBMForecaster`; it asks for `"gru"` and gets a `NeuralForecastAdapter` wrapping a `GRUForecaster`. Zero conditional logic in the pipeline.

**Why**: Adding a new model strategy (say, XGBoost) means writing one new file and adding one line in `bootstrap.py`. No `if model_name == "xgboost":` branches anywhere.

```python
# bootstrap.py -- the only file that knows all concrete implementations
factories = {
    "sarimax": SARIMAXForecaster,
    "lightgbm": LightGBMForecaster,
    "mlp": _neural_factory(MLPForecaster),
    "gru": _neural_factory(GRUForecaster),
    "cnn": _neural_factory(CNNForecaster),
}
```

### 3. Template Method Pattern

**Where**: `models/deep/base.py`

**What it does**: `BaseNeuralForecaster` owns the entire PyTorch training loop -- device placement, Adam optimizer, MSE loss, per-epoch tracking, early stopping with patience, best-weights restoration. Children override only `build_network()` (return the architecture) and `forward()` (run a forward pass).

**Why**: The training loop is invariant across GRU, CNN, and MLP. Without this, every child would duplicate ~100 lines of boilerplate, creating three places where bugs could diverge. This matches how PyTorch Lightning's `LightningModule` and `pytorch-forecasting`'s `BaseModel` work internally.

**Result**: Each child model is under 50 lines of code (including docstrings and imports) containing only its unique architecture:

| Child | Lines | What makes it different |
|-------|-------|------------------------|
| `MLPForecaster` | 34 | Flatten + 2 linear layers. The "dumb baseline" you must beat. |
| `GRUForecaster` | 46 | Multi-layer GRU + linear head. Reads sequence step-by-step. |
| `CNNForecaster` | 44 | 3-layer dilated 1D conv (mini TCN). Reads local windows in parallel. |

### 4. Adapter Pattern

**Where**: `models/deep/adapter.py`

**What it does**: `NeuralForecastAdapter` implements the `ForecastModel` port (pandas in, `ForecastBatch` out) and delegates to a `BaseNeuralForecaster` instance (tensors in, tensors out). It handles:
- Feature standardization (mean/std stored for inference)
- DataFrame -> `SlidingWindowDataset` -> `DataLoader` conversion
- Chronological 80/20 train/val split (no shuffling -- time series!)
- Tensor -> `Forecast` objects back-conversion

**Why this is the most important file for learning**: It is the single place where "pandas world" meets "tensor world." Every type transition is visible in one ~90-line file. The inner neural net stays pure PyTorch; the outer pipeline stays pure pandas. Neither contaminates the other.

### 5. Registry / Factory

**Where**: `models/registry.py`

**What it does**: A simple dict-based registry that maps model name strings to callable factories. `registry.create("gru", symbol="POWER_DE")` returns a fully configured model instance.

**Why**: Decouples the pipeline from construction details. The CLI, scheduler, and trainer all resolve models by name without importing concrete classes.

---

## Model Families

### Why three families?

The SARIMAX + LightGBM + Deep Learning trio is the documented industry standard for electricity price forecasting (validated in [SARIMAX to Deep Learning: Energy Forecasting](https://medium.com/@sabya_sachi/sarimax-to-deep-learning-energy-forecasting-53c1bb114506) and [ML/DL comparative study for UK electricity prices](https://link.springer.com/article/10.1007/s43926-024-00075-4)). Each family has distinct strengths:

### 1. SARIMAX (Classical Statistics)

**File**: `models/classical/arima.py`

**Library**: statsmodels

**What it does**: Seasonal AutoRegressive Integrated Moving Average with eXogenous factors. Fits on the univariate VWAP series. Emits native confidence intervals via `get_forecast().conf_int()`.

**Strengths**:
- **Interpretable** -- the (p,d,q)(P,D,Q,s) orders have clear statistical meaning
- **Native uncertainty quantification** -- confidence bands come free from the model, not estimated post-hoc
- **Works with small data** -- can produce reasonable forecasts with weeks of history

**Weaknesses**:
- Univariate only (ignores exogenous features like volume, LMP components)
- Assumes linear relationships
- Slow to fit on long series

**Default configuration**: `order=(2,1,2)`, `seasonal_order=(1,0,1,24)` -- two autoregressive and two moving-average terms with first-order differencing, plus a daily seasonal cycle.

**Use case**: Short-term (hourly/daily) price forecasting where interpretability matters and you need confidence intervals for risk management.

### 2. LightGBM (Gradient Boosting)

**File**: `models/gradient/lightgbm_model.py`

**Library**: LightGBM

**What it does**: Three separate gradient-boosted regressors for the 10th, 50th, and 90th percentiles (quantile regression). This gives you `yhat_lower`, `yhat` (median), and `yhat_upper` as native confidence bands -- the same technique used by M5 competition winners.

**Strengths**:
- **Uses all features** -- lags, rolling stats, calendar, LMP components
- **Fast training** -- orders of magnitude faster than neural nets
- **Handles mixed feature types** naturally
- **Built-in quantile regression** for confidence intervals
- **Feature importance** available for interpretability

**Weaknesses**:
- Recursive prediction for multi-step horizons (error compounds)
- No built-in sequential awareness (treats each sample independently)

**Default configuration**: 31 leaves, 0.05 learning rate, 200 estimators, min 20 child samples.

**Use case**: The workhorse. Best accuracy-to-compute ratio for most energy price forecasting tasks. First model to try on any new dataset.

### 3. Deep Learning (GRU / CNN / MLP)

**Files**: `models/deep/base.py`, `gru.py`, `cnn.py`, `mlp.py`, `adapter.py`

**Library**: PyTorch (CPU-only in Docker)

**Three architectural paradigms, one base class:**

#### MLP (Multi-Layer Perceptron) -- the dumb baseline

Flattens the entire sliding window `(seq_len x features)` into a single vector, feeds it through two linear layers. Provides no sequential awareness whatsoever. **The industry rule: if your GRU/CNN can't beat this on a held-out set, something is wrong with your data or features.**

#### GRU (Gated Recurrent Unit)

Reads the input sequence one timestep at a time, maintaining a hidden state that summarizes what it has seen so far. At the end of the sequence, the final hidden state feeds through a linear head to produce the forecast.

Compared to LSTM, GRU has one fewer gate (reset + update vs. input + forget + output) and slightly fewer parameters, but near-identical accuracy on time-series tasks -- the standard recommendation for learning.

#### CNN (1D Dilated Convolutions -- mini TCN)

Three Conv1d layers with increasing dilation rates (1, 2, 4) read progressively larger temporal neighborhoods. Every output position is computed in parallel (no sequential dependency), so training is significantly faster than GRU on modern hardware. Adaptive average pooling compresses the temporal dimension before a linear head.

**Weaknesses (all neural)**:
- Need more data than classical or gradient methods
- No native confidence intervals (point forecasts only)
- Require feature standardization
- Black-box (less interpretable)

**Use case**: Research and experimentation. When you have enough data and want to capture complex non-linear temporal patterns that LightGBM might miss. The MLP baseline tells you whether the added complexity is worth it.

---

## Feature Engineering

**File**: `features/builder.py`

The `FeatureBuilder` is a **pure function** -- no I/O, no state, no side effects. Input: raw `trade_aggregates` rows from the database. Output: a `FeatureFrame` ready for training or inference.

### Feature families produced

| Family | Columns | Purpose |
|--------|---------|---------|
| **Raw passthrough** | `vwap`, `total_volume`, `trade_count`, `max_price`, `min_price` | Base signal |
| **Lags** | `vwap_lag_{1,5,15,30,60}`, `volume_lag_{1,5,15}` | Autoregressive memory |
| **Rolling stats** | `vwap_roll_mean_{5,15,60}`, `vwap_roll_std_{5,15,60}` | Trend + volatility |
| **Log returns** | `log_return_1`, `log_return_5`, `realized_vol_15` | Stationarity + volatility clustering |
| **Calendar (cyclical)** | `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`, `is_weekend` | Time-of-day / day-of-week seasonality |
| **Spread** | `price_range = max_price - min_price` | Intra-window volatility |
| **LMP components** | `lmp_energy`, `lmp_congestion`, `lmp_loss` | Energy market fundamentals |

### Why cyclical encoding?

Hour 23 and hour 0 are 1 hour apart in reality, but 23 units apart as raw integers. Sin/cos encoding maps them onto a unit circle where their Euclidean distance correctly reflects their temporal proximity. Same logic for day-of-week.

### FeatureFrame

```python
@dataclass(frozen=True)
class FeatureFrame:
    data: pd.DataFrame              # Full DataFrame with features + target
    feature_columns: tuple[str, ...]  # Which columns are features (not the target)
    target: str = "vwap"            # Name of the target column
    feature_hash: str               # SHA-256 of sorted feature names
```

The `feature_hash` is a deterministic fingerprint of the feature set. It is stamped onto every `Forecast` object and into the `model_registry`, so two predictions made with different feature definitions can never be mistaken for each other.

### NaN handling

Rows with NaN in any feature column are **dropped** -- this is intentional. A model must never train on incomplete lag features (e.g., the first 60 rows have no `vwap_lag_60`). The builder drops these rows after computing all features, producing a clean rectangular matrix.

---

## Anomaly Detection

### IsolationForest Detector

**File**: `models/anomaly/iforest.py`

Wraps `sklearn.ensemble.IsolationForest`. Unsupervised: learns the "normal" distribution from historical features and flags rows that sit in sparse regions of the 4D feature space (`vwap`, `total_volume`, `price_range`, `lmp_congestion`).

- `decision_function` returns a signed score (flipped so higher = weirder)
- `predict` returns -1 (anomaly) or 1 (normal)
- Configurable contamination rate (default 1%)

**Use case**: First line of defense in market surveillance. Catches price spikes, volume explosions, and unusual LMP congestion patterns without needing labeled anomaly data.

### Residual Anomaly Detector

**File**: `models/anomaly/residual.py`

**Composition over inheritance**: takes any `Baseline` callable (a rolling mean by default, or any `ForecastModel`) and computes:

```
residual = actual - baseline_prediction
is_anomaly = |residual - mean_residual| > k * sigma_residual
```

where `mean` and `sigma` are learned from training-set residuals (classic 3-sigma rule).

**Why composition**: The detector holds a reference to its inner baseline and never inherits from it. Swap a rolling mean for a SARIMAX forecaster without touching the detection logic. This is the Decorator / Strategy hybrid that production anomaly systems use.

**Use case**: If you already have a good forecaster, you get an anomaly detector for free. Anything the model gets badly wrong is, by construction, unusual.

---

## Training Pipeline

**File**: `pipeline/trainer.py`

Single class `TrainingPipeline` with one method `run(model_name, symbol)`:

```
1. Load history       FeatureRepository.load_history(symbol, start, end)
                      |
2. Build features     FeatureBuilder.build(raw) -> FeatureFrame
                      |
3. Walk-forward eval  WalkForwardSplitter.split(ff, n_folds=3)
                      For each fold:
                        a. model = registry.create(model_name)
                        b. model.fit(train_X, train_y)
                        c. preds = model.predict(val_X, horizon)
                        d. metrics = compute_all(val_y, preds)
                      |
4. Final fit          Fit on all data
                      |
5. Persist            model.save(model_store) -> artifact_uri
                      |
6. Register           model_registry_repo.save(metadata)
```

**Every step emits a structlog event.** The pipeline has zero conditional logic for different model types -- everything resolves through the `ForecastModel` protocol and the registry.

---

## Evaluation Strategy

**File**: `pipeline/evaluation.py`

### Walk-forward cross-validation

**Not random k-fold.** Random splits leak future information into the training set and produce wildly optimistic metrics. Walk-forward is the **only valid approach for time series**:

```
Fold 1:  [=====TRAIN=====][==VAL==]....................
Fold 2:  [=========TRAIN=========][==VAL==]..........
Fold 3:  [=============TRAIN=============][==VAL==]..
```

Each validation window immediately follows its training window in time. Training grows monotonically across folds (the model always sees at least `min_train_size` rows).

### Metric suite

| Metric | Formula | Why |
|--------|---------|-----|
| **MAE** | mean(\|y - y_hat\|) | Intuitive, same units as price. Primary metric. |
| **RMSE** | sqrt(mean((y - y_hat)^2)) | Penalizes large errors more than MAE. |
| **MAPE** | mean(\|y - y_hat\| / \|y\|) * 100 | Percentage-based, comparable across scales. |
| **sMAPE** | mean(\|y - y_hat\| / ((y + y_hat) / 2)) * 100 | Symmetric MAPE, bounded [0, 200], handles zeros. |
| **Pinball** | quantile loss for probabilistic forecasts | Evaluates the quality of confidence bands. |

All implemented as pure functions -- easiest possible unit tests.

---

## Data Contracts

### Domain Models (`domain/models.py`)

All Pydantic v2 with `frozen=True` (immutable).

| Model | Purpose | Key fields |
|-------|---------|-----------|
| `Forecast` | Single predicted value | `symbol`, `forecast_for`, `yhat` (Decimal 18,8), `yhat_lower`, `yhat_upper`, `model_name`, `model_version`, `feature_hash` |
| `ForecastBatch` | Collection from one inference call | `forecasts: list[Forecast]` |
| `AnomalyScore` | Single anomaly signal | `symbol`, `window_start`, `score`, `is_anomaly`, `detector_name` |
| `ModelMetadata` | Training run lineage | `model_name`, `model_version`, `trained_at`, `metrics`, `params`, `artifact_uri` |

**Precision**: All prices use `Decimal(18,8)` to match the `trade_aggregates` table. No floating-point drift between the trading and forecasting layers.

**Timestamps**: All datetimes are validated to UTC. Naive datetimes are automatically promoted to UTC via `field_validator`.

---

## Database Schema

**File**: `sql/schema/007_create_ml_tables.sql`

Three tables:

| Table | Type | Primary Key | Purpose |
|-------|------|-------------|---------|
| `forecasts` | Hypertable (time-partitioned by `forecast_for`) | `(symbol, forecast_for, model_name, model_version)` | Stores every forecast. Two model versions can run simultaneously -- Grafana shows both. |
| `anomaly_scores` | Hypertable (time-partitioned by `window_start`) | `(symbol, window_start, detector_name)` | One row per (symbol, window, detector). |
| `model_registry` | Plain table | `(model_name, model_version)` | Lineage: params + metrics + artifact URI for every training run. |

**Why hypertables**: `forecasts` and `anomaly_scores` grow unbounded (one row per minute-ahead step per model per symbol). TimescaleDB hypertables provide automatic time-partitioning and compression. `model_registry` is low-volume (one row per training run) so a plain table suffices.

---

## Container Topology

| Container | Image | ML deps? | Role |
|-----------|-------|----------|------|
| `api` | `docker/api/Dockerfile` | **No** | Read-only REST endpoints. Lean, fast cold start. |
| `ml-scheduler` | `docker/ml/Dockerfile` | **Yes** (torch, lgb, stats, sklearn) | Long-running APScheduler cron that retrains and writes forecasts. |
| `ml-trainer` | `docker/ml/Dockerfile` | **Yes** (same image) | One-shot training runs via `trade-ml train`. |

The ML containers are gated behind the `ml` compose profile: `docker-compose up` without `--profile ml` leaves the forecasting stack dormant. The core trading platform is unaffected.

---

## API Reference

All endpoints are read-only. The API container queries tables that ML workers populate.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/forecasts/{symbol}?model=lightgbm&horizon=15` | Latest forecast batch. Returns `yhat`, `yhat_lower`, `yhat_upper`. |
| `GET` | `/api/v1/anomalies/{symbol}?hours=24&only_flagged=true` | Anomaly scores within the lookback window. |
| `GET` | `/api/v1/models` | All trained model versions with metrics and artifact URIs. |

### Example response: `/api/v1/forecasts/POWER_DE`

```json
{
  "symbol": "POWER_DE",
  "model_name": "lightgbm",
  "model_version": "20260412T020000Z",
  "forecasts": [
    {
      "symbol": "POWER_DE",
      "forecast_for": "2026-04-12T03:01:00Z",
      "generated_at": "2026-04-12T02:00:15Z",
      "horizon_minutes": 1,
      "yhat": "45.12345678",
      "yhat_lower": "42.50000000",
      "yhat_upper": "47.80000000",
      "model_name": "lightgbm",
      "model_version": "20260412T020000Z",
      "feature_hash": "a3f8c2..."
    }
  ]
}
```

---

## Configuration

**File**: `config.py`

All settings are 12-factor env-overridable with the `ML_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `ML_MODEL_NAME` | `lightgbm` | Default model strategy |
| `ML_HORIZON_MINUTES` | `15` | Forecast horizon |
| `ML_SEQ_LEN` | `60` | Sliding window length for neural models |
| `ML_SYMBOLS` | `["POWER_DE"]` | Symbols to train on |
| `ML_TRAIN_HISTORY_DAYS` | `30` | Days of history for training |
| `ML_EVAL_FOLDS` | `3` | Walk-forward CV folds |
| `ML_RETRAIN_CRON` | `0 2 * * *` | Daily 02:00 UTC retraining |
| `ML_MODEL_STORE_PATH` | `data/ml_models` | Artifact storage directory |
| `ML_HIDDEN_SIZE` | `64` | Neural net hidden dimension |
| `ML_NUM_LAYERS` | `2` | GRU layer count |
| `ML_DROPOUT` | `0.1` | Neural dropout rate |
| `ML_BATCH_SIZE` | `64` | Training batch size |
| `ML_EPOCHS` | `50` | Max training epochs |
| `ML_LEARNING_RATE` | `0.001` | Adam learning rate |
| `ML_EARLY_STOPPING_PATIENCE` | `5` | Early stopping patience |

---

## Usage

### Prerequisites

- Docker and Docker Compose
- PowerShell (recommended on Windows) or bash

### 1. Apply the ML schema

```powershell
cd JanAndFeb
docker-compose up -d postgres

docker-compose exec -T postgres psql -U trading -d trades < sql/schema/007_create_ml_tables.sql
```

### 2. Build the ML image

```powershell
docker-compose --profile ml build ml-scheduler
```

### 3. One-shot training (learning / experimentation)

```powershell
# Train each of the 5 strategies
docker-compose --profile ml run --rm ml-trainer trade-ml train --model sarimax  --symbol POWER_DE
docker-compose --profile ml run --rm ml-trainer trade-ml train --model lightgbm --symbol POWER_DE
docker-compose --profile ml run --rm ml-trainer trade-ml train --model gru      --symbol POWER_DE
docker-compose --profile ml run --rm ml-trainer trade-ml train --model cnn      --symbol POWER_DE
docker-compose --profile ml run --rm ml-trainer trade-ml train --model mlp      --symbol POWER_DE
```

Each writes:
- 1 artifact under `data/ml_models/{model_name}/{version}/`
- 1 row to `model_registry`
- N rows to `forecasts` (where N = horizon)

### 4. Start the automated retraining scheduler

```powershell
docker-compose --profile ml up -d ml-scheduler
```

The scheduler retrains every model for every configured symbol on a cron schedule (default: daily 02:00 UTC).

### 5. Query via the API

```powershell
# Latest forecast
curl "http://localhost:8000/api/v1/forecasts/POWER_DE?model=lightgbm&horizon=15"

# Anomalies in the last 6 hours
curl "http://localhost:8000/api/v1/anomalies/POWER_DE?hours=6"

# All trained models with metrics
curl "http://localhost:8000/api/v1/models"
```

### 6. Local development (without Docker for ML)

```powershell
conda activate energy-trading
pip install -e ".[dev,ml]"

# Postgres still needs Docker
docker-compose up -d postgres

# Train locally
trade-ml train --model lightgbm --symbol POWER_DE

# Start scheduler locally
trade-ml schedule
```

---

## Taking It Apart

This section is for learning. It shows how to poke at individual pieces
interactively, inspect what they produce, and understand the data at
each stage of the pipeline.

### Inspect trained artifacts on disk

After a training run, artifacts land under `data/ml_models/`:

```
data/ml_models/
  lightgbm/
    20260412T020000Z/
      model.bin          # joblib-serialized LGBMRegressor dict
      metadata.json      # hparams, feature columns, feature hash
  gru/
    20260412T021500Z/
      model.bin          # torch state_dict + hparams + scaler stats
      metadata.json
```

Read the metadata sidecar to see exactly what was trained:

```powershell
cat data/ml_models/lightgbm/*/metadata.json | python -m json.tool
```

### Explore features in a Python REPL / notebook

```python
import pandas as pd
from src.ml.features.builder import FeatureBuilder

# Simulate raw trade_aggregates (or load from DB)
raw = pd.read_sql("SELECT * FROM trade_aggregates WHERE symbol = 'POWER_DE' ORDER BY window_start LIMIT 500", conn)

# Build features -- see every column that gets created
fb = FeatureBuilder()
ff = fb.build(raw)

print(f"Rows after NaN drop: {len(ff)}")
print(f"Feature columns ({len(ff.feature_columns)}):")
for col in ff.feature_columns:
    print(f"  {col}")
print(f"Target: {ff.target}")
print(f"Feature hash: {ff.feature_hash}")

# Inspect the actual data
ff.x.describe()   # feature matrix stats
ff.y.describe()   # target stats
ff.data.head(10)  # full DataFrame with features + target
```

### Train a single model and inspect outputs

```python
from src.ml.models.gradient.lightgbm_model import LightGBMForecaster

model = LightGBMForecaster(symbol="POWER_DE")
metadata = model.fit(ff.x, ff.y)

print(f"Model: {metadata.model_name} v{metadata.model_version}")
print(f"Training MAE: {metadata.metrics.get('train_mae', 'N/A')}")

# Predict 15 minutes ahead
batch = model.predict(ff.x, horizon=15)
for f in batch.forecasts[:5]:
    print(f"  {f.forecast_for} -> yhat={f.yhat}, CI=[{f.yhat_lower}, {f.yhat_upper}]")
```

### Compare model families side-by-side

```python
from src.ml.models.classical.arima import SARIMAXForecaster
from src.ml.models.gradient.lightgbm_model import LightGBMForecaster
from src.ml.models.deep.adapter import NeuralForecastAdapter
from src.ml.models.deep.gru import GRUForecaster

models = {
    "sarimax": SARIMAXForecaster(symbol="POWER_DE"),
    "lightgbm": LightGBMForecaster(symbol="POWER_DE"),
    "gru": NeuralForecastAdapter(
        net_cls=GRUForecaster,
        hparams={"hidden_size": 64, "num_layers": 2, "dropout": 0.1, "seq_len": 60, "horizon": 15},
        symbol="POWER_DE",
        epochs=20,  # fewer epochs for quick experimentation
    ),
}

for name, model in models.items():
    meta = model.fit(ff.x, ff.y)
    batch = model.predict(ff.x, horizon=15)
    print(f"{name:12s} -> metrics={meta.metrics}, first_yhat={batch.forecasts[0].yhat}")
```

### Inspect the neural training loop

```python
from src.ml.models.deep.gru import GRUForecaster
from src.ml.models.deep.datasets import SlidingWindowDataset
from torch.utils.data import DataLoader
import numpy as np

# Build a dataset manually
x = ff.x.astype(float).values
y = ff.y.astype(float).values
mean, std = x.mean(axis=0), x.std(axis=0)
x_norm = (x - mean) / np.where(std < 1e-8, 1.0, std)

ds = SlidingWindowDataset(x_norm, y, seq_len=60, horizon=15)
print(f"Dataset length: {len(ds)}")
print(f"Window shape: {ds[0][0].shape}")   # (60, n_features)
print(f"Target shape: {ds[0][1].shape}")   # (15,)

# Build the network and inspect it
net = GRUForecaster(hparams={
    "input_size": x.shape[1], "hidden_size": 64,
    "num_layers": 2, "dropout": 0.1, "horizon": 15, "seq_len": 60,
})
print(net.network)  # shows the GRU + Linear architecture

# Run the training loop with verbose output
loader = DataLoader(ds, batch_size=32, shuffle=True)
metrics = net.fit_loader(loader, epochs=5, learning_rate=1e-3)
print(f"Final train loss: {metrics['train_loss']:.6f}")
```

### Run anomaly detection interactively

```python
from src.ml.models.anomaly.iforest import IsolationForestDetector

detector = IsolationForestDetector(symbol="POWER_DE", contamination=0.02)
detector.fit(ff.data.iloc[:-10])  # train on all but last 10 rows

scores = detector.score(ff.data)
anomalies = [s for s in scores if s.is_anomaly]
print(f"Total rows: {len(scores)}, Anomalies: {len(anomalies)}")
for a in anomalies[:5]:
    print(f"  {a.window_start} score={a.score:.3f}")
```

### Run the evaluation suite on any model

```python
from src.ml.pipeline.evaluation import compute_all, WalkForwardSplitter
import numpy as np

splitter = WalkForwardSplitter(n_folds=3, min_train_size=200, horizon=15)

for fold_idx, (train_ff, val_ff) in enumerate(splitter.split(ff)):
    model = LightGBMForecaster(symbol="POWER_DE")
    model.fit(train_ff.x, train_ff.y)
    batch = model.predict(val_ff.x, horizon=len(val_ff))

    y_true = val_ff.y.to_numpy()
    y_pred = np.array([float(f.yhat) for f in batch.forecasts[:len(y_true)]])
    metrics = compute_all(y_true, y_pred)
    print(f"Fold {fold_idx}: {metrics}")
```

### Save and reload a model

```python
from src.ml.store.filesystem import FilesystemModelStore
from pathlib import Path

store = FilesystemModelStore(root=Path("data/ml_models"))

# Save
uri = model.save(store)
print(f"Saved to: {uri}")

# Load into a fresh instance
from src.ml.models.gradient.lightgbm_model import LightGBMForecaster
loaded = LightGBMForecaster.load(store, uri)
batch2 = loaded.predict(ff.x, horizon=15)
print(f"Loaded model predicts: {batch2.forecasts[0].yhat}")
```

### Query the database directly

```sql
-- Latest forecasts per model
SELECT model_name, model_version, COUNT(*) as forecast_count,
       MIN(forecast_for) as first, MAX(forecast_for) as last
FROM forecasts
GROUP BY model_name, model_version
ORDER BY MAX(generated_at) DESC;

-- Model registry -- all training runs with metrics
SELECT model_name, model_version, trained_at,
       metrics->>'mae' as mae, metrics->>'rmse' as rmse,
       artifact_uri
FROM model_registry
ORDER BY trained_at DESC;

-- Anomaly events in the last 24 hours
SELECT symbol, window_start, score, detector_name
FROM anomaly_scores
WHERE is_anomaly = true AND window_start > NOW() - INTERVAL '24 hours'
ORDER BY score DESC;

-- Compare two model versions side-by-side
SELECT a.forecast_for, a.yhat as v1_yhat, b.yhat as v2_yhat,
       ABS(a.yhat - b.yhat) as diff
FROM forecasts a
JOIN forecasts b ON a.symbol = b.symbol AND a.forecast_for = b.forecast_for
WHERE a.model_version = '20260412T020000Z'
  AND b.model_version = '20260413T020000Z'
ORDER BY a.forecast_for;
```

### Run unit tests selectively

```powershell
# Run just one test file
docker-compose --profile ml run --rm --user 0 --entrypoint python `
  -v "${PWD}:/workspace" -w /workspace ml-trainer `
  -m pytest tests/unit/ml/test_lightgbm.py -v

# Run tests matching a pattern
docker-compose --profile ml run --rm --user 0 --entrypoint python `
  -v "${PWD}:/workspace" -w /workspace ml-trainer `
  -m pytest tests/unit/ml -v -k "iforest"

# Run with full coverage report
docker-compose --profile ml run --rm --user 0 --entrypoint python `
  -v "${PWD}:/workspace" -w /workspace ml-trainer `
  -m pytest tests/unit/ml -v --cov=src/ml --cov-report=term-missing
```

---

## Quality Gates

### Inside the ML container (recommended)

```powershell
cd JanAndFeb
docker-compose --profile ml run --rm --user 0 --entrypoint python `
  -v "${PWD}:/workspace" -w /workspace ml-trainer `
  /workspace/scripts/run_ml_gates.py
```

This runs:
1. `ruff check src/ml tests/unit/ml` -- linting
2. `mypy src/ml --strict --follow-imports=silent` -- strict type checking (ML code only)
3. `pytest tests/unit/ml -v --cov=src/ml` -- 52 unit tests with coverage

### Current status

| Gate | Status |
|------|--------|
| ruff check | All checks passed |
| mypy --strict | Success: 37 source files, 0 errors |
| pytest | 52 passed, 0 failed |
| Coverage | 69% (unit tests cover models, features, evaluation, domain; wiring code needs integration tests) |

---

## File Map

### Source (26 files + 11 `__init__.py`)

| File | Lines | Purpose |
|------|-------|---------|
| `src/ml/config.py` | 71 | MLSettings (Pydantic BaseSettings, env-overridable) |
| `src/ml/main.py` | 149 | CLI entry point (`trade-ml train`, `trade-ml schedule`) |
| `src/ml/bootstrap.py` | 88 | Model registration + loader wiring |
| `src/ml/domain/models.py` | 133 | Forecast, ForecastBatch, AnomalyScore, ModelMetadata |
| `src/ml/domain/ports.py` | 124 | ForecastModel, AnomalyDetector, ModelStore, repositories |
| `src/ml/features/schema.py` | 52 | FeatureFrame (typed pandas wrapper + hash) |
| `src/ml/features/builder.py` | 117 | FeatureBuilder -- pure function, all feature families |
| `src/ml/features/repository.py` | 88 | SQLFeatureRepository -- reads trade_aggregates |
| `src/ml/models/registry.py` | 50 | ModelRegistry: name -> factory dict |
| `src/ml/models/classical/arima.py` | 168 | SARIMAXForecaster (statsmodels) |
| `src/ml/models/gradient/lightgbm_model.py` | 190 | LightGBMForecaster (quantile regression) |
| `src/ml/models/deep/base.py` | 223 | BaseNeuralForecaster -- Template Method |
| `src/ml/models/deep/adapter.py` | 241 | NeuralForecastAdapter -- DataFrame <-> Tensor bridge |
| `src/ml/models/deep/datasets.py` | 52 | SlidingWindowDataset (torch Dataset) |
| `src/ml/models/deep/gru.py` | 46 | GRUForecaster |
| `src/ml/models/deep/cnn.py` | 44 | CNNForecaster (dilated 1D conv) |
| `src/ml/models/deep/mlp.py` | 34 | MLPForecaster (flatten + dense baseline) |
| `src/ml/models/anomaly/iforest.py` | 111 | IsolationForestDetector (sklearn) |
| `src/ml/models/anomaly/residual.py` | 155 | ResidualAnomalyDetector (composition-based) |
| `src/ml/pipeline/trainer.py` | 194 | TrainingPipeline (walk-forward + persist) |
| `src/ml/pipeline/inference.py` | 109 | InferenceService (load, predict, cache) |
| `src/ml/pipeline/evaluation.py` | 130 | MAE, RMSE, MAPE, sMAPE, pinball, WalkForwardSplitter |
| `src/ml/pipeline/scheduler.py` | 82 | APScheduler cron loop |
| `src/ml/store/filesystem.py` | 83 | FilesystemModelStore (joblib/torch + JSON sidecar) |
| `src/ml/store/repository.py` | 194 | PostgresForecastRepository, ModelRegistryRepository |
| `src/ml/api/routes.py` | 174 | FastAPI router (read-only, mounted at /api/v1) |

### Tests (11 files, 52 tests)

| File | Tests | What it covers |
|------|-------|---------------|
| `test_domain_models.py` | 6 | Pydantic validation, UTC coercion, immutability |
| `test_feature_builder.py` | 6 | Feature families, cyclical encoding, NaN handling, hashing |
| `test_evaluation.py` | 11 | All 5 metrics + walk-forward splitter properties |
| `test_registry.py` | 4 | Register, create, duplicate, unknown-name errors |
| `test_filesystem_store.py` | 4 | Save/load roundtrip, exists, missing-raises |
| `test_arima.py` | 3 | Fit, predict, save/load roundtrip |
| `test_lightgbm.py` | 3 | Fit, predict, save/load roundtrip |
| `test_deep.py` | 7 | SlidingWindow shapes, child forward shapes (x3 parametrized), base fit converges, adapter roundtrip |
| `test_iforest.py` | 3 | Spike detection, fit-before-score, missing columns |
| `test_residual_anomaly.py` | 4 | Large-jump detection, quiet-on-clean, fit-before-score, missing target |
| `test_trainer.py` | 1 | End-to-end training pipeline with mock repos |

### Schema

| File | Purpose |
|------|---------|
| `sql/schema/007_create_ml_tables.sql` | `forecasts`, `anomaly_scores`, `model_registry` |

### Infrastructure

| File | Purpose |
|------|---------|
| `docker/ml/Dockerfile` | Multi-stage build for ml-trainer/ml-scheduler |
| `scripts/run_ml_gates.py` | Helper to run quality gates inside the container |
| `monitoring/grafana/provisioning/dashboards/forecasts.json` | Grafana dashboard |

---

## Design Decisions & Trade-offs

| Decision | Trade-off | Why |
|----------|-----------|-----|
| **Handwritten ModelStore instead of MLflow** | More code to maintain | Every moving part visible for learning; swap to MLflow via the `ModelStore` port later |
| **CPU-only PyTorch in Docker** | Slower neural training | Simpler image, no CUDA dependency, neural models are small enough for CPU |
| **Recursive prediction (LightGBM)** | Error compounds over horizon | Simpler than direct multi-output; keeps feature engineering identical between train and serve |
| **GRU over LSTM** | Marginally less expressive | One fewer gate, near-identical accuracy, simpler to reason about for learning |
| **No Transformer** | Missing the newest architecture | GRU, CNN, MLP already demonstrate three distinct paradigms; Transformer can be added as a 4th child later |
| **Walk-forward only (no random CV)** | Fewer folds possible with small data | Non-negotiable for time series -- random splits leak future information |
| **Split containers (lean API + fat ML)** | More complex deployment | API stays fast; ML stack can be upgraded independently; production-standard separation |
| **`feature_hash` on every prediction** | Small storage overhead | Two predictions with different feature sets can never be confused; essential for A/B comparison |
