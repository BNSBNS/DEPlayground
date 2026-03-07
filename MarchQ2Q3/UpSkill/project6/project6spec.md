# Project 6: ML Feature Store

## What This Is
A feature store that handles the full lifecycle of ML features: define features as SQL/Python transformations, compute them on schedule (batch) or in real-time (streaming), version them, serve them at low latency for inference, and monitor for drift. It bridges data engineering and ML engineering — the infrastructure that makes or breaks ML in production.

Think: a data engineer defines a feature like "customer_order_count_30d". The feature store computes it nightly (batch), updates it in seconds when a new order arrives (stream), serves it in <10ms for real-time model inference, tracks its distribution over time, and alerts when it drifts.

## Career Relevance
- **ML Engineering:** This IS core ML infrastructure — feature stores are the #1 bottleneck in ML teams. Point-in-time joins, training-serving skew prevention, and feature drift detection are the hard problems MLEs solve daily.
- **Data Engineering:** Dual compute path (batch SQL + streaming Kafka) is a textbook lambda architecture. Feature pipelines are data pipelines with stricter SLAs.
- **Platform Engineering:** Low-latency serving (<10ms p99), versioning, and monitoring are production platform concerns.
- **AI Engineering:** Feature quality directly determines model quality — drift detection using PSI/KS tests shows statistical rigor.
- The complete project mirrors what Feast, Tecton, and Featureform build as products.

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Feature definitions | Python DSL + SQL | Declarative feature specs |
| Batch compute | PostgreSQL / DuckDB | SQL-based batch feature computation |
| Stream compute | aiokafka consumer | Async Kafka consumer for real-time updates. NOT Faust (unmaintained). |
| Offline store | PostgreSQL (or Parquet files) | Historical feature values for training |
| Online store | Redis | Low-latency serving for inference |
| API | FastAPI | Feature serving, management, monitoring |
| Monitoring | Prometheus + Grafana + custom | Drift, freshness, serving latency |
| Registry | PostgreSQL | Feature metadata, versions, lineage, ownership |
| Event source | Kafka (Redpanda) | Streaming feature source |

## Folder Structure

```
feature-store/
├── docker-compose.yml          # app, batch-worker, stream-worker, postgres, redis, redpanda, prometheus, grafana
├── pyproject.toml
├── .env.example
├── Makefile
├── README.md
├── src/
│   ├── config.py
│   ├── models/                 # FeatureDefinition, FeatureSet, FeatureValue, Entity, DataSource
│   ├── registry/               # Feature catalog, versioning, lineage, dependency resolution
│   ├── definitions/            # DSL parser, SQL features, Python features, validators
│   ├── compute/
│   │   ├── batch/              # Batch engine: SQL executor, scheduler, backfill
│   │   └── stream/             # Stream engine: aiokafka consumer, real-time aggregations
│   ├── storage/
│   │   ├── offline_store.py    # PostgreSQL/Parquet: historical values for training
│   │   └── online_store.py     # Redis: latest values for serving
│   ├── serving/                # Feature server: point-in-time lookup, batch retrieval
│   ├── monitoring/             # Drift detector, freshness checker, data quality
│   ├── api/
│   └── db/
├── frontend/
│   ├── app/                    # Feature catalog, feature detail, monitoring dashboard
│   └── components/             # FeatureCard, DriftChart, LineageGraph, ServingStats
├── simulation/
│   ├── seed.py                 # Sample features, entities, 90 days historical data
│   ├── simulator.py            # Events triggering real-time features + drift injection
│   ├── sample_features/        # YAML/Python feature definitions
│   ├── ml_example/             # Train + serve a model using the feature store
│   └── README.md
├── tests/
├── grafana/dashboards/
├── prometheus/
└── k8s/
```

## Core Concepts

### Entity
The thing features describe. Has a type and a join key.
- Examples: `customer` (join key: customer_id), `product` (join key: product_id), `order` (join key: order_id)
- Features are always computed per entity

### Feature
A single computed value for an entity at a point in time.
- Example: `customer_order_count_30d` = count of orders for a customer in the last 30 days

### Feature Set
A group of related features computed from the same source.
- Example: `customer_order_features` → order_count_7d, order_count_30d, avg_order_value_30d, last_order_days_ago
- All features in a set share the same entity, source, and compute schedule

### Data Source
Where raw data comes from.
- Batch source: a table or SQL query (e.g., `SELECT * FROM orders`)
- Stream source: a Kafka topic (e.g., `order_events`)
- A feature set can have BOTH a batch and a stream source — batch for backfill/training, stream for real-time updates

## Data Models

### FeatureDefinition
- `name` — unique identifier (e.g., "customer_order_count_30d")
- `feature_set` — which set this belongs to
- `entity` — entity type + join key column
- `value_type` — enum: int64, float64, string, bool, timestamp, json
- `description`, `owner`, `tags`
- `batch_source` — SQL query or table reference for batch compute
- `stream_source` — Kafka topic for real-time compute (optional)
- `aggregation` — for time-windowed features: function (count/sum/avg/min/max/last), window (7d/30d/90d), timestamp_column
- `transform` — for non-aggregation features: SQL expression or Python callable reference
- `freshness_sla` — max acceptable staleness (e.g., "1 hour" for batch, "30 seconds" for streaming)
- `version`, `created_at`, `updated_at`, `status` (active/deprecated/experimental)

### FeatureValue
- `entity_key` — the entity's ID value (e.g., "customer_123")
- `feature_name`
- `value` — the computed value (stored as JSONB for type flexibility)
- `event_timestamp` — when the underlying data event occurred
- `created_timestamp` — when this value was computed

### TrainingDataset
- `id`, `name`, `entity_type`
- `features` — list of feature names to include
- `entity_df` — reference to entity DataFrame with keys + event timestamps
- `created_at`, `row_count`

### FeatureStats
- `feature_name`, `window_start`, `window_end`
- `count`, `null_count`, `null_pct`
- `mean`, `stddev`, `min`, `max`, `p25`, `p50`, `p75`, `p95`
- `unique_count` (for categorical)
- `value_distribution` — JSONB: histogram bins or top-N values

## Feature Definition DSL

Features can be defined two ways:

**SQL-based** (for batch features):
Features are defined in YAML files with SQL expressions. The batch engine executes these queries against the batch source, grouped by entity key.

A YAML feature definition includes: feature set name, entity reference, batch source (table or query), and a list of features each with a name, aggregation function, window, and optional filter.

**Python-based** (for complex transforms):
For features requiring logic beyond SQL (e.g., text processing, custom business rules), define a Python function decorated with a `@feature` marker. The function receives a row or batch and returns the computed value. These are registered in the feature catalog alongside SQL features.

The DSL validator checks: entity references are valid, source tables/topics exist, aggregation functions are supported, windows are parseable, value types are consistent.

## Core Logic

### Registry (`src/registry/`)
- **Feature catalog** — CRUD for features and feature sets. Search by name, entity, owner, tag.
- **Version manager** — Track definition changes. Breaking (value_type change, entity change) → major bump, keep old serving until consumers migrate. Non-breaking (description, tag) → minor bump.
- **Lineage tracker** — Source tables/topics → features → consuming models. Impact analysis: "if this table changes, which features and models break?"
- **Dependency resolver** — Features can depend on other features (derived features). Resolve computation order with topological sort. Detect circular dependencies.

### Batch Compute (`src/compute/batch/`)
- **BatchEngine** — For a given feature set: (1) read batch source, (2) compute each feature's aggregation/transform grouped by entity key, (3) write to offline store with event_timestamp AND update online store with latest value.
- **Scheduler** — Configurable per feature set. Default daily, support hourly for high-freshness needs.
- **Backfill** — Compute historical values for a date range. Essential for: initial setup, new features, recomputation after bug fixes. Iterates over time windows to build complete history.
- **Point-in-time joins** — When building training data: for each (entity_key, event_timestamp) pair, find the most recent feature value where `feature.event_timestamp <= requested_timestamp`. This prevents training-serving skew. Implementation: SQL window function with `ROW_NUMBER()` partitioned by entity, ordered by event_timestamp DESC, filtered to <= requested timestamp.

### Stream Compute (`src/compute/stream/`)
- **StreamEngine** — aiokafka consumer that: (1) consumes events from stream source topic, (2) extracts entity key and timestamp, (3) updates running aggregations, (4) writes updated value to online store.
- **Window aggregations** — Maintain state in Redis:
  - count/sum: store bucketed counts (e.g., hourly buckets for a 30-day window). Sum across non-expired buckets. Expire old buckets via Redis TTL or explicit cleanup.
  - avg: store running count + running sum, divide on read.
  - min/max: store Redis sorted set, trim entries outside window.
  - last: simple overwrite.
- **Consistency model** — Stream provides freshness (seconds), batch provides accuracy (recomputed from source of truth). Batch periodically overwrites online store values, correcting any drift from the streaming approximation. This is the standard lambda architecture tradeoff.

### Storage (`src/storage/`)

**Offline Store** (PostgreSQL or Parquet):
- Stores ALL historical feature values with timestamps
- Used for: training data generation, backfill, auditing
- Schema: (entity_key, feature_name, value, event_timestamp, created_timestamp)
- Partitioned by event_timestamp for efficient range queries
- Point-in-time query: given (entity_key, timestamp) pairs → feature values current at each timestamp

**Online Store** (Redis):
- Stores ONLY the latest value per entity per feature
- Used for: real-time inference serving
- Key format: `feature:{feature_name}:{entity_key}` → JSON {value, event_timestamp, created_timestamp}
- TTL based on freshness SLA (expire stale values so consumers don't use outdated features)
- Batch retrieval: Redis pipeline for multiple features per entity in one round trip

### Serving (`src/serving/`)
- **Online serving** — Input: entity key(s) + feature list → return latest values from Redis. Must be < 10ms p99. Return metadata: feature version, freshness, last updated. Flag stale features.
- **Batch serving** — Input: entity DataFrame (keys + timestamps) + feature list → point-in-time correct values from offline store. Used for training dataset generation.
- **Training dataset builder** — Accepts entity DataFrame + feature list + optional time range. Returns complete training dataset with point-in-time correct joins. This is the core value proposition: it prevents training-serving skew automatically.

### Monitoring (`src/monitoring/`)
- **Freshness checker** — For each feature: compare latest event_timestamp in online store vs now. If staleness > SLA → alert.
- **Drift detector** — Compare current distribution (last 1hr/1day) against reference (last 30 days).
  - Numeric features: Population Stability Index (PSI). PSI > 0.1 → warning, > 0.2 → critical.
  - Categorical features: chi-squared test. p-value < 0.05 → warning, < 0.01 → critical.
  - PSI formula: PSI = Σ (actual_pct - expected_pct) × ln(actual_pct / expected_pct) across histogram bins.
- **Data quality** — Track null rates, out-of-range values, cardinality changes.
- **Serving metrics** — Latency percentiles, request volume per feature, cache hit rate.

## Simulation

### seed.py
- E-commerce tables: customers (5000), orders (50000), products (200), clickstream (100000)
- Register 20 features across 4 feature sets:
  - `customer_order_features`: order_count_7d, order_count_30d, order_count_90d, avg_order_value_30d, total_spend_lifetime, last_order_days_ago, unique_products_purchased_30d
  - `customer_activity_features`: session_count_7d, page_views_30d, add_to_cart_rate_30d, last_active_days_ago
  - `product_features`: total_sales_30d, avg_rating, view_count_7d, conversion_rate_30d, return_rate_90d
  - `order_features`: item_count, has_discount, payment_method, is_first_order
- Backfill 90 days of historical values into offline store
- Populate online store with latest values
- Seed 30 days of FeatureStats for monitoring baselines

### simulator.py (continuous)
- Generate new orders and clickstream events via Kafka at 10-50 events/sec
- Stream engine updates features in real time
- Every 5 minutes: inject a drift scenario (gradually shift order values up, change category distribution)
- Every 15 minutes: batch engine runs, corrects streaming state
- Monitor detects drift, logs alerts

### sample_features/
- YAML/Python definitions for all 20 features
- Serves as both documentation and input to registration API

### ml_example/
- Python script demonstrating end-to-end ML workflow:
  1. Connect to feature store API
  2. Build training dataset: entity keys + timestamps → point-in-time features
  3. Train a scikit-learn classifier (predict customer churn based on order + activity features)
  4. Use online serving API for real-time inference on new customers
  5. Log feature importance, compare to feature store metadata
- Shows the complete value loop: data → features → model → predictions

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/features` | List features (filter by entity, owner, set, tag) |
| POST | `/api/v1/features` | Register feature definition |
| GET | `/api/v1/features/{name}` | Feature detail + stats + lineage |
| PUT | `/api/v1/features/{name}` | Update feature (triggers version bump) |
| POST | `/api/v1/features/{name}/backfill` | Trigger backfill for date range |
| GET | `/api/v1/feature-sets` | List feature sets |
| POST | `/api/v1/feature-sets` | Create feature set |
| POST | `/api/v1/serve/online` | Get latest feature values for entity key(s) |
| POST | `/api/v1/serve/training` | Build training dataset (entity df + features → point-in-time) |
| GET | `/api/v1/monitoring/freshness` | Feature freshness status |
| GET | `/api/v1/monitoring/drift` | Drift detection results |
| GET | `/api/v1/monitoring/stats/{name}` | Historical distribution stats |
| POST | `/api/v1/compute/batch/trigger` | Manually trigger batch compute |
| GET | `/api/v1/compute/status` | Batch/stream compute status |
| GET | `/health` | Health check |

## Docker Compose Services
- `app` — FastAPI feature server + management API
- `batch-worker` — Batch compute engine (scheduled)
- `stream-worker` — aiokafka consumer for real-time features
- `postgres` — Registry + offline store
- `redis` — Online store
- `redpanda` — Event source for streaming features
- `prometheus` + `grafana` — Monitoring dashboards
- `frontend` — Next.js feature catalog + monitoring

## Implementation Phases

### Phase 1: Registry + Definitions
Feature/FeatureSet/Entity/DataSource models. YAML parser. Registry CRUD. Validator. seed.py. **Success:** register features, browse catalog via API.

### Phase 2: Batch Compute + Offline Store
BatchEngine with SQL execution. PostgreSQL offline store. Backfill for date ranges. **Success:** compute 20 features for 5000 customers with timestamps.

### Phase 3: Online Store + Serving
Redis online store. Online serving endpoint (<10ms). Batch serving with point-in-time joins. Training dataset builder. **Success:** serve features for inference, build a training dataset.

### Phase 4: Stream Compute
aiokafka consumer with real-time aggregation. Sliding window state in Redis. Batch consistency reconciliation. **Success:** new order → customer features updated in Redis within 5 seconds.

### Phase 5: Monitoring + Drift Detection
Freshness checker, PSI/chi-squared drift detector, data quality tracking, serving metrics. **Success:** simulate distribution shift → drift alert fires.

### Phase 6: Frontend + ML Example + Simulation
Feature catalog UI, monitoring dashboard. ml_example script (train + serve using feature store). Full simulator.py with drift scenarios. **Success:** end-to-end ML workflow using the feature store.

## Metrics
- Online serving p99: < 10ms (single entity, 10 features)
- Online serving p99: < 50ms (batch of 100 entities)
- Batch compute throughput: > 10K entities/minute
- Stream update latency: < 5 seconds (event → online store)
- Training dataset generation: < 30 seconds for 100K rows × 20 features
- Drift detection latency: < 5 minutes
- Freshness SLA compliance: > 99%