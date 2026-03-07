# Project 4: Real-Time Streaming Analytics Platform

## What This Is
A streaming data platform that ingests events from Kafka, processes them through transformation and enrichment layers, serves aggregated results via a low-latency query API, and displays real-time dashboards.

## Career Relevance
- **Data Engineering:** Streaming is the biggest skill gap in most DE portfolios — Kafka expertise is consistently top-3 in job requirements
- **ML Engineering:** Real-time feature pipelines feed ML inference systems — this is the event backbone for Project 6 (Feature Store)
- **AI Engineering:** Anomaly detection on streaming data is a core applied AI pattern
- Understanding streaming architecture (consumer groups, at-least-once delivery, backpressure) is essential for any real-time data or ML system

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Message broker | Apache Kafka (via Redpanda) | Redpanda is Kafka API-compatible, no JVM, lighter for dev |
| Stream processing | aiokafka | Async Python Kafka client. NOT Faust (unmaintained since 2020). |
| Enrichment | Redis | Fast lookups for reference data joins |
| Serving store | PostgreSQL + Redis | Materialized aggregates for fast reads |
| API | FastAPI | REST + WebSocket for live updates |
| Frontend | Next.js | Real-time dashboard with live charts |
| Monitoring | Prometheus + Grafana | Consumer lag, throughput, latency |
| Schema | Redpanda Schema Registry (built-in) | Avro/JSON Schema event validation |

## Folder Structure

```
streaming-analytics/
├── docker-compose.yml          # app, redpanda, redis, postgres, grafana, prometheus
├── pyproject.toml
├── .env.example
├── Makefile
├── README.md
├── src/
│   ├── config.py
│   ├── models/                 # Event schemas (Pydantic), aggregation models, serving models
│   ├── producers/              # Event producers (simulation + real connectors)
│   ├── consumers/              # aiokafka consumers with processing logic
│   ├── processors/             # Transformation, enrichment, aggregation logic
│   ├── serving/                # Materialized view manager, query layer
│   ├── api/                    # FastAPI REST + WebSocket
│   └── db/
├── frontend/
│   ├── app/                    # Dashboard, event explorer
│   └── components/             # LiveChart, EventStream, MetricCard
├── simulation/
│   ├── seed.py                 # Reference data (products, customers, regions)
│   ├── simulator.py            # Continuous event producer
│   ├── scenarios/              # Predefined: normal, flash_sale, fraud_spike, outage_recovery
│   └── README.md
├── tests/
├── grafana/dashboards/
├── prometheus/
└── k8s/
```

## Domain Model: E-Commerce Event Stream

### Event Types (Kafka topics)
- **order_events** — order_id, customer_id, product_ids, total_amount, currency, status (placed/confirmed/shipped/delivered/cancelled), timestamp
- **clickstream_events** — session_id, customer_id, page, action (view/click/search/add_to_cart), product_id, timestamp
- **payment_events** — payment_id, order_id, amount, method, status (pending/completed/failed/refunded), timestamp
- **inventory_events** — product_id, warehouse_id, quantity_change, reason (sale/restock/adjustment), timestamp

### Reference Data (Redis, seeded)
- Products: id, name, category, price, supplier
- Customers: id, tier (bronze/silver/gold/platinum), region, signup_date
- Regions: id, name, timezone, currency

### Materialized Aggregates (PostgreSQL serving tables)
- **real_time_sales** — rolling 1min/5min/1hr revenue, order count, avg order value, by region
- **customer_activity** — last seen, session count today, cart value, status
- **product_performance** — views, add_to_carts, purchases, conversion rate, rolling 1hr
- **anomaly_flags** — flagged events with reason (large order, rapid clicks, failed payment streak)

## Core Logic

### Producers (`src/producers/`)
- Abstract EventProducer base with `produce(topic, key, event)` using `AIOKafkaProducer`
- JSON serialization via Pydantic `.model_dump_json()`
- Production mode: webhook receivers, CDC connectors
- Simulation mode: reads from simulator.py

### Consumers (`src/consumers/`)
Each consumer is an async task using `AIOKafkaConsumer` with manual offset commit (at-least-once delivery).

- **OrderConsumer** — Consumes `order_events`, enriches with customer data from Redis, updates `real_time_sales` aggregate.
- **ClickstreamConsumer** — Consumes `clickstream_events`, maintains session state in Redis (TTL-based expiry), updates `customer_activity` and `product_performance`.
- **PaymentConsumer** — Consumes `payment_events`, correlates with orders via order_id lookup, detects failed payment streaks (3+ consecutive failures).
- **AnomalyConsumer** — Consumes all topics via pattern subscription, applies rule-based detection.

### Processors (`src/processors/`)
- **Enricher** — Look up customer/product reference data from Redis, attach to event. Handle cache misses gracefully (skip enrichment, log warning).
- **Aggregator** — Tumbling and sliding window aggregations (1min, 5min, 1hr). Running state in Redis hashes (key per window per dimension), flush to PostgreSQL periodically. Use Redis INCRBY/INCRBYFLOAT for atomic increments.
- **AnomalyDetector** — Rules: order amount > 3x customer average, click rate > 100/min per session, 3+ consecutive payment failures per customer. Flag and write to `anomaly_flags`.

### Serving (`src/serving/`)
- Materialized view manager: upsert aggregated results to PostgreSQL serving tables
- Query layer: fast reads with time-range and dimension filters
- WebSocket manager: push updates to connected clients when aggregates change

## Simulation

### seed.py
- 100 products across 5 categories, realistic names and prices
- 500 customers across 4 tiers, 6 regions
- 3 warehouses with initial inventory

### simulator.py (continuous)
- Configurable rate (default 50-100 events/sec across all topics)
- Realistic patterns: daily volume curve, 70% clicks don't convert, 3-5% payment failure rate
- **Scenarios** (`--scenario` flag):
  - `normal` — typical day
  - `flash_sale` — 5x order spike for 10 minutes on specific products
  - `fraud_spike` — burst of high-value orders from new accounts
  - `outage_recovery` — 5 minutes silence, then backlog flood

### fixtures/
- Static JSON event batches per topic (100 events each) for unit tests

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/sales/realtime` | Current sales metrics (period filter) |
| GET | `/api/v1/products/performance` | Product leaderboard |
| GET | `/api/v1/customers/{id}/activity` | Customer session/activity |
| GET | `/api/v1/anomalies` | Recent anomaly flags |
| WS | `/api/v1/ws/sales` | Live sales updates |
| WS | `/api/v1/ws/events` | Live event stream |
| GET | `/api/v1/topics` | Kafka topics and consumer lag |
| GET | `/health` | Health check |

## Docker Compose Services
- `redpanda` — Kafka-compatible (9092 broker, 8081 schema registry, 8080 console)
- `app` — FastAPI API server
- `worker` — Consumer processes (can be split or combined with app)
- `redis` — Reference cache + aggregation state
- `postgres` — Serving tables
- `prometheus` + `grafana` — Consumer lag, throughput dashboards
- `frontend` — Next.js dashboard

## Implementation Phases

### Phase 1: Kafka + Producers
Redpanda setup, event Pydantic models, producer with aiokafka, seed.py. **Success:** events visible in Redpanda Console (http://localhost:8080).

### Phase 2: Consumers + Enrichment
OrderConsumer and ClickstreamConsumer, Redis enrichment, basic aggregation. **Success:** enriched events logged, basic counts in Redis.

### Phase 3: Aggregation + Serving
Window aggregations (Redis state), materialized PostgreSQL tables, query layer. **Success:** REST API returns real-time sales.

### Phase 4: Anomaly Detection
Rule-based detector, anomaly_flags table, configurable thresholds. **Success:** simulated fraud spike triggers flags.

### Phase 5: Live Dashboard
WebSocket endpoints, Next.js with live charts, event stream viewer. **Success:** dashboard updates in real time.

### Phase 6: Simulation Scenarios
Full simulator.py, Grafana dashboards for consumer lag + throughput. **Success:** `make simulate scenario=flash_sale` shows system reaction.

## Metrics
- End-to-end latency (produced → serving table): < 2 seconds
- Consumer throughput: > 1000 events/sec per consumer
- Query API p95: < 100ms
- WebSocket update frequency: < 1 second
- Consumer lag recovery (flash_sale): < 2 minutes