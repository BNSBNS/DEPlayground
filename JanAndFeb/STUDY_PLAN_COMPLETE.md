# Complete Data Engineering Study Plan
## Energy Trading Platform - Streaming Analytics

This is the comprehensive, fact-checked study plan covering all critical areas. Content has been verified against the actual codebase.

---

# TABLE OF CONTENTS

1. [Part 1: Architecture Overview](#part-1-architecture-overview)
2. [Part 2: Streaming (Kafka)](#part-2-streaming-kafka)
3. [Part 3: Observability (Grafana & Prometheus)](#part-3-observability-grafana--prometheus)
4. [Part 4: Analytics (Superset)](#part-4-analytics-superset)
5. [Part 5: Data Layer (TimescaleDB)](#part-5-data-layer-timescaledb)
6. [Part 6: Critical Issues & Bugs](#part-6-critical-issues--bugs)
7. [Part 7: Reliability Patterns](#part-7-reliability-patterns)
8. [Part 8: API & Integration](#part-8-api--integration)
9. [Part 9: Testing & Validation](#part-9-testing--validation)
10. [Part 10: Chaos Testing Framework](#part-10-chaos-testing-framework)
11. [Part 11: Failure Scenarios & Runbooks](#part-11-failure-scenarios--runbooks)
12. [Part 12: Design Patterns](#part-12-design-patterns)
13. [Part 13: Common Issues & Resolution Guide](#part-13-common-issues--resolution-guide)
14. [Part 14: Quick Reference](#part-14-quick-reference)

---

# PART 1: ARCHITECTURE OVERVIEW

## 1.1 System Architecture

```
┌─────────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│  Trade Producer │────▶│      Apache Kafka       │────▶│  Trade Consumer  │
│  (10 trades/sec)│     │  Topic: "trades" (6p)   │     │  (Windowed Agg)  │
│                 │     │  Topic: "trades-dlq"    │     │                  │
└─────────────────┘     └─────────────────────────┘     └────────┬─────────┘
                                                                 │
                        ┌────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TimescaleDB (PostgreSQL)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ trade_aggregates│  │   raw_trades    │  │  dlq_messages   │         │
│  │ (1-min VWAP)    │  │ (NOT POPULATED) │  │ (error tracking)│         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Grafana    │ │   Superset   │ │  REST API    │
│  (Metrics)   │ │ (Analytics)  │ │ (WebSocket)  │
│  Port 3000   │ │  Port 8088   │ │  Port 8000   │
└──────────────┘ └──────────────┘ └──────────────┘
```

## 1.2 Key Components

| Component | Purpose | Port | Key Files |
|-----------|---------|------|-----------|
| Producer | Generates synthetic trades | 8002 (metrics) | `src/producer/` |
| Consumer | Aggregates into 1-min windows | 8001 (metrics) | `src/consumer/` |
| Kafka | Message broker | 9092 | `docker-compose.yml` |
| Kafka UI | Message inspection | 8080 | - |
| TimescaleDB | Time-series storage | 5432 | `sql/schema/` |
| Grafana | Operational dashboards | 3000 | `monitoring/grafana/` |
| Superset | Business analytics | 8088 | - |
| Prometheus | Metrics collection | 9090 | `monitoring/prometheus.yml` |
| API | REST + WebSocket | 8000 | `src/api/` |

## 1.3 Data Flow

```
1. Producer generates TradeEvent
   - UUID trade_id, symbol, price, volume, side, trader_id, timestamp
   - 10/sec normal, 50/sec during burst (every 5 min for 30 sec)

2. Kafka receives message
   - Key: symbol (ensures ordering per symbol)
   - Partition: Determined by key hash (6 partitions)

3. Consumer processes message
   - Deserializes JSON → TradeEvent (Pydantic validation)
   - Routes to WindowedAggregator
   - Window: 1-minute tumbling, aligned to minute boundary

4. Window closes (watermark > window_end + 30s grace)
   - Computes: VWAP, total_volume, trade_count, max_price, min_price
   - Writes to PostgreSQL with idempotent upsert

5. Offset committed ONLY after successful DB write
   - At-least-once delivery guarantee
```

---

# PART 2: STREAMING (KAFKA)

## 2.1 Core Concepts

| Term | Definition | In This Project |
|------|------------|-----------------|
| **Topic** | Logical channel for messages | `trades`, `trades-dlq` |
| **Partition** | Parallelism unit within topic | 6 partitions for `trades` |
| **Offset** | Position of message in partition | Used for at-least-once delivery |
| **Consumer Group** | Group of consumers sharing work | `trade-aggregator` |
| **Message Key** | Determines partition routing | Symbol (e.g., `POWER_DE`) |
| **Watermark** | Tracks event time progress | Latest event timestamp |

## 2.2 Producer Deep Dive

**Files**: [kafka_producer.py](src/producer/kafka_producer.py), [trade_generator.py](src/producer/trade_generator.py)

**Key Patterns**:

```python
# Delivery callback pattern (verified in code)
def delivery_callback(err, msg):
    if err:
        logger.error(f"Delivery failed: {err}")
    else:
        logger.debug(f"Delivered to {msg.topic()}[{msg.partition()}]")

producer.produce(topic, key=symbol, value=json_bytes, callback=delivery_callback)
producer.poll(0)  # Trigger callbacks without blocking
```

**Configuration** (from [config.py](src/common/config.py)):
- Rate: 10 trades/sec (configurable)
- Burst: 5x multiplier, 30 sec duration, every 5 min
- Symbols: POWER_DE, POWER_FR, POWER_NL, GAS_NL, GAS_UK, BRENT_OIL, CARBON_EU

## 2.3 Consumer Deep Dive

**Files**: [kafka_consumer.py](src/consumer/kafka_consumer.py), [windowed_aggregator.py](src/consumer/windowed_aggregator.py)

**Processing Flow** (verified at [kafka_consumer.py:105-170](src/consumer/kafka_consumer.py#L105-L170)):

```python
def _process_message(self, msg: Message) -> None:
    # 1. Parse and validate
    trade = self._parse_message(msg)  # Pydantic validation

    # 2. Add to aggregator, get completed windows
    completed_aggregates = self._aggregator.add_trade(trade)

    # 3. Write completed aggregates to database
    if completed_aggregates:
        self._db_writer.write_aggregates_batch(completed_aggregates)

    # 4. Commit offset ONLY after successful DB write
    self._consumer.commit(msg)
```

**Critical**: Offset committed AFTER DB write = at-least-once delivery.

## 2.4 Windowed Aggregation

**File**: [windowed_aggregator.py](src/consumer/windowed_aggregator.py)

**Window Logic** (verified):
- **Type**: Tumbling windows (non-overlapping)
- **Duration**: 60 seconds (configurable)
- **Alignment**: Minute boundary (10:00:00, 10:01:00, etc.)
- **Grace Period**: 30 seconds for late events
- **Max Windows**: 1000 (prevents memory leak)

**VWAP Calculation** (verified at [windowed_aggregator.py:51-62](src/consumer/windowed_aggregator.py#L51-L62)):
```python
def compute_vwap(self) -> Decimal:
    if self.total_volume == 0:
        return Decimal("0")
    vwap = self.total_value / self.total_volume  # sum(price*volume) / sum(volume)
    return vwap.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
```

## 2.5 Common Streaming Issues

| Issue | Symptoms | Root Cause | Solution | Detection |
|-------|----------|------------|----------|-----------|
| Consumer Lag | Stale dashboards | Processing slower than production | Scale consumers, optimize processing | `kafka-consumer-groups --describe` |
| Rebalancing Storm | Frequent partition reassignment | Short session timeout | Increase `session.timeout.ms` | Logs: "rebalance" |
| Serialization Error | Consumer crashes | Malformed JSON | DLQ pattern (implemented) | Check `trades-dlq` topic |
| Out-of-Order Events | Incorrect VWAP | Network delays | Use event timestamp (implemented) | Compare event_timestamp vs processing time |

## 2.6 Hands-On: Kafka Testing

**Start the Stack**:
```bash
cd JanAndFeb
docker-compose -f docker-compose-full.yml up -d
```

**Inspect Topics**:
```bash
# List topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe trades topic
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic trades

# Consume messages directly
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic trades \
  --from-beginning \
  --max-messages 5
```

**Check Consumer Lag**:
```bash
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group trade-aggregator
```

**Test DLQ**:
```bash
# Send malformed message
echo '{"invalid": "json"}' | docker exec -i kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic trades

# Check DLQ
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic trades-dlq \
  --from-beginning
```

---

# PART 3: OBSERVABILITY (GRAFANA & PROMETHEUS)

## 3.1 Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producer   │     │  Consumer   │     │    API      │
│  :8002      │     │  :8001      │     │  :8000      │
│  /metrics   │     │  /metrics   │     │  /metrics   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                   ┌───────────────┐
                   │  Prometheus   │
                   │  :9090        │
                   │  (scrapes)    │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │   Grafana     │
                   │   :3000       │
                   │  (visualizes) │
                   └───────────────┘
```

## 3.2 Prometheus Configuration

**File**: [prometheus.yml](monitoring/prometheus.yml)

```yaml
scrape_configs:
  - job_name: "trade-consumer"
    static_configs:
      - targets: ["consumer:8001"]

  - job_name: "trade-producer"
    static_configs:
      - targets: ["producer:8002"]
```

## 3.3 Metrics Exposed

**Consumer Metrics** (from [metrics.py](src/consumer/metrics.py)):

| Metric | Type | Description |
|--------|------|-------------|
| `messages_processed_total` | Counter | Total messages processed by symbol |
| `aggregates_written_total` | Counter | Aggregates written to DB |
| `dlq_messages_total` | Counter | Messages sent to DLQ |
| `processing_duration_seconds` | Histogram | Time to process each message |
| `db_write_duration_seconds` | Histogram | Time to write to database |
| `active_windows` | Gauge | Currently open aggregation windows |
| `data_freshness_seconds` | Gauge | Age of most recent event |

## 3.4 PromQL Query Examples

```promql
# Trades processed per second (rate over 5 minutes)
rate(messages_processed_total[5m])

# 95th percentile processing latency
histogram_quantile(0.95, rate(processing_duration_seconds_bucket[5m]))

# Active windows (should be < 1000)
active_windows

# DLQ rate (should be ~0)
rate(dlq_messages_total[5m])

# Data freshness (should be < 60 seconds)
data_freshness_seconds
```

## 3.5 Grafana Setup

**Access**: http://localhost:3000 (admin/admin)

**Add PostgreSQL Data Source**:
1. Configuration → Data Sources → Add
2. Select PostgreSQL
3. Settings:
   - Host: `postgres:5432` (use `localhost:5432` if outside Docker)
   - Database: `trades`
   - User: `trading`
   - Password: `trading`
   - TLS/SSL Mode: disable
4. Save & Test

**Create Dashboard Panel (VWAP Time Series)**:
1. Dashboards → New Dashboard → Add Panel
2. Data source: PostgreSQL
3. Query:
```sql
SELECT
    window_start AS "time",
    symbol,
    vwap AS "value"
FROM trade_aggregates
WHERE $__timeFilter(window_start)
ORDER BY window_start
```
4. Visualization: Time series
5. Panel options: Title = "VWAP by Symbol"

**Create Alert Rule**:
1. Alerting → Alert Rules → Create
2. Query: `data_freshness_seconds > 120`
3. Condition: Is above 120 for 2 minutes
4. Labels: severity=warning

## 3.6 Common Grafana Issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| No data in panel | Empty graph | Check data source connection, verify time range |
| Missing Prometheus targets | Targets show "DOWN" | Verify service is running, check network |
| Time zone mismatch | Data shifted | Dashboard Settings → Time Options → UTC |
| Query too slow | Loading forever | Add time filter, reduce data points |

## 3.7 Hands-On: Grafana Testing

**Verify Prometheus Targets**:
```bash
# Check targets via API
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

**Test Metrics Endpoints**:
```bash
# Consumer metrics
curl -s http://localhost:8001/metrics | head -20

# Producer metrics
curl -s http://localhost:8002/metrics | head -20
```

**Query Prometheus Directly**:
```bash
# Get current active windows
curl 'http://localhost:9090/api/v1/query?query=active_windows'

# Get processing rate
curl 'http://localhost:9090/api/v1/query?query=rate(messages_processed_total[5m])'
```

---

# PART 4: ANALYTICS (SUPERSET)

## 4.1 Superset vs Grafana

| Aspect | Grafana | Superset |
|--------|---------|----------|
| Primary Use | Operational monitoring | Business analytics |
| Users | DevOps, SRE | Analysts, Business |
| Data Sources | Time-series (Prometheus) | SQL databases |
| Strength | Real-time metrics, alerts | Ad-hoc SQL, exploration |
| Query Language | PromQL | SQL |

## 4.2 Initial Setup

**Access**: http://localhost:8088

**First-Time Initialization**:
```bash
# Create admin user
docker exec -it superset superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@example.com \
  --password admin

# Initialize database
docker exec -it superset superset db upgrade
docker exec -it superset superset init
```

**Add Database Connection**:
1. Settings → Database Connections → + Database
2. Select PostgreSQL
3. SQLAlchemy URI: `postgresql://trading:trading@postgres:5432/trades`
4. Test Connection → Connect

## 4.3 Create Dataset

1. Data → Datasets → + Dataset
2. Database: trades
3. Schema: public
4. Table: trade_aggregates
5. Add

**Configure Dataset**:
- Mark `window_start` as temporal column
- Mark `vwap`, `total_volume`, `trade_count` as metrics

## 4.4 Build Charts

**Chart 1: VWAP Time Series**
1. Charts → + Chart
2. Dataset: trade_aggregates
3. Chart Type: Time-series Line Chart
4. Time Column: window_start
5. Time Grain: Minute
6. Metrics: AVG(vwap)
7. Dimensions: symbol
8. Filters: Last 1 hour

**Chart 2: Volume by Symbol**
1. Chart Type: Bar Chart
2. Metrics: SUM(total_volume)
3. Dimensions: symbol
4. Sort: Descending by metric

## 4.5 SQL Lab Queries

**Current VWAP by Symbol**:
```sql
SELECT
    symbol,
    vwap,
    total_volume,
    trade_count,
    window_start
FROM trade_aggregates
WHERE window_start = (
    SELECT MAX(window_start) FROM trade_aggregates
)
ORDER BY total_volume DESC;
```

**Hourly Trend (Using Continuous Aggregate)**:
```sql
SELECT
    bucket AS hour,
    symbol,
    hourly_vwap,
    hourly_volume,
    hourly_trades
FROM cagg_hourly_vwap
WHERE bucket > NOW() - INTERVAL '24 hours'
ORDER BY bucket DESC, symbol;
```

**Top Trading Minutes**:
```sql
SELECT
    window_start,
    SUM(trade_count) AS total_trades,
    SUM(total_volume) AS total_volume
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY window_start
ORDER BY total_trades DESC
LIMIT 10;
```

## 4.6 Common Superset Issues

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Connection failed | "Can't connect to database" | Use `postgres` not `localhost` inside Docker |
| Query timeout | Charts won't load | Add LIMIT, use continuous aggregates |
| Permission denied | Can't create charts | Need Alpha or Admin role |
| Stale data | Old values showing | Dashboard → Force Refresh, check cache settings |

---

# PART 5: DATA LAYER (TIMESCALEDB)

## 5.1 Schema Design

**File**: [001_create_trade_aggregates.sql](sql/schema/001_create_trade_aggregates.sql)

```sql
CREATE TABLE trade_aggregates (
    symbol VARCHAR(20) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    -- NUMERIC for financial precision (not FLOAT!)
    vwap NUMERIC(18, 8) NOT NULL,
    total_volume NUMERIC(18, 8) NOT NULL,
    trade_count INTEGER NOT NULL,
    max_price NUMERIC(18, 8) NOT NULL,
    min_price NUMERIC(18, 8) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (symbol, window_start)  -- Enables idempotent upserts
);
```

**Why NUMERIC(18,8)?**
- 18 total digits, 8 after decimal
- Exact arithmetic (no floating-point errors)
- Critical for financial calculations

## 5.2 TimescaleDB Features

**File**: [003_timescaledb_setup.sql](sql/schema/003_timescaledb_setup.sql)

**Hypertable Conversion**:
```sql
SELECT create_hypertable(
    'trade_aggregates',
    'window_start',
    chunk_time_interval => INTERVAL '1 day'
);
```

**Compression Policy** (data older than 7 days):
```sql
ALTER TABLE trade_aggregates SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'window_start DESC'
);

SELECT add_compression_policy('trade_aggregates', compress_after => INTERVAL '7 days');
```

**Continuous Aggregates** (pre-computed hourly/daily):
```sql
-- Hourly VWAP (auto-refreshing)
CREATE MATERIALIZED VIEW cagg_hourly_vwap
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', window_start) AS bucket,
    symbol,
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS hourly_vwap,
    SUM(total_volume) AS hourly_volume,
    SUM(trade_count) AS hourly_trades
FROM trade_aggregates
GROUP BY time_bucket('1 hour', window_start), symbol;

-- Refresh every 5 minutes
SELECT add_continuous_aggregate_policy('cagg_hourly_vwap',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes'
);
```

## 5.3 Idempotent Upsert Pattern

**File**: [db_writer.py:31-48](src/consumer/db_writer.py#L31-L48)

```sql
INSERT INTO trade_aggregates (...)
VALUES (...)
ON CONFLICT (symbol, window_start) DO UPDATE SET
    vwap = EXCLUDED.vwap,          -- REPLACES (not accumulates)
    total_volume = EXCLUDED.total_volume,
    trade_count = EXCLUDED.trade_count,
    max_price = EXCLUDED.max_price,
    min_price = EXCLUDED.min_price,
    updated_at = NOW()
```

**When This Works**: Replay scenarios (same window reprocessed)
**When This Fails**: Late events after window eviction (see Part 6)

## 5.4 Performance Queries

**Check Chunk Status**:
```sql
SELECT
    hypertable_name,
    chunk_name,
    range_start,
    range_end,
    is_compressed
FROM timescaledb_information.chunks
WHERE hypertable_name = 'trade_aggregates'
ORDER BY range_start DESC
LIMIT 10;
```

**Check Compression Ratio**:
```sql
SELECT
    pg_size_pretty(before_compression_total_bytes) AS before,
    pg_size_pretty(after_compression_total_bytes) AS after,
    ROUND((1 - after_compression_total_bytes::float /
           NULLIF(before_compression_total_bytes, 0)::float) * 100, 1) AS compression_pct
FROM hypertable_compression_stats('trade_aggregates');
```

**Analyze Query Performance**:
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT symbol, AVG(vwap), SUM(total_volume)
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY symbol;

-- Look for "Chunks excluded" in output
```

---

# PART 6: CRITICAL ISSUES & BUGS

## 6.1 CRITICAL: Late Event Data Corruption

### The Bug (VERIFIED)

**Source**: [windowed_aggregator.py:156-169](src/consumer/windowed_aggregator.py#L156-L169)

**What Happens**:
```
Timeline:
T+0:00   Window 10:00-10:01 created
T+1:00   100 trades processed, VWAP calculated
T+1:30   Window closes (watermark > window_end + 30s grace)
         - Correct aggregate written to DB (100 trades)
         - Window state DELETED from memory
T+5:00   Late trade arrives, event_timestamp = 10:00:30
         - Key not in self._windows
         - NEW EMPTY WindowState() created
         - Only 1 trade added
T+6:30   New window flushes
         - VWAP calculated from 1 trade (WRONG!)
         - DB UPDATE REPLACES correct aggregate

Result: 100-trade VWAP destroyed, replaced with 1-trade VWAP
```

**Code Evidence**:
```python
# windowed_aggregator.py:156-162
if key not in self._windows:
    self._windows[key] = WindowState()  # NEW EMPTY window
    logger.debug("Created new window", ...)

# Line 169
self._windows[key].add_trade(trade)  # Only late trade added
```

### Root Cause Analysis

| Question | Answer |
|----------|--------|
| **Why?** | Window state evicted after grace period; late event creates new empty window |
| **Impact** | DATA CORRUPTION - correct aggregate overwritten |
| **Detection** | Windows with low trade_count that were updated after creation |
| **Prevention** | Persist state in Redis, or check DB before creating window |
| **Resolution** | Replay from Kafka if retention allows |

### Detection Query

```sql
-- Find potentially corrupted windows
WITH symbol_stats AS (
    SELECT
        symbol,
        AVG(trade_count) AS avg_trades,
        STDDEV(trade_count) AS stddev_trades
    FROM trade_aggregates
    WHERE window_start > NOW() - INTERVAL '24 hours'
    GROUP BY symbol
)
SELECT
    a.symbol,
    a.window_start,
    a.trade_count,
    a.created_at,
    a.updated_at,
    ROUND(s.avg_trades, 1) AS avg_trades,
    CASE
        WHEN a.trade_count < s.avg_trades - 2 * s.stddev_trades
        THEN 'SUSPICIOUS'
        ELSE 'OK'
    END AS status
FROM trade_aggregates a
JOIN symbol_stats s ON a.symbol = s.symbol
WHERE a.updated_at > a.created_at + INTERVAL '1 minute'
ORDER BY a.updated_at DESC
LIMIT 20;
```

### Validation Test

```python
# test_late_event_corruption.py
import json
import time
from datetime import datetime, timedelta, UTC
from confluent_kafka import Producer

producer = Producer({'bootstrap.servers': 'localhost:9092'})

# Step 1: Note the current minute
window_time = datetime.now(UTC).replace(second=0, microsecond=0)

# Step 2: Send 50 normal trades
for i in range(50):
    trade = {
        "trade_id": f"NORMAL-{i}",
        "symbol": "TEST_CORRUPT",
        "price": "100.00",
        "volume": "100.00",
        "side": "BUY",
        "trader_id": "TESTER",
        "event_timestamp": (window_time + timedelta(seconds=i % 60)).isoformat()
    }
    producer.produce('trades', key='TEST_CORRUPT', value=json.dumps(trade))
producer.flush()
print(f"Sent 50 trades for window {window_time}")

# Step 3: Wait for window to close (2+ minutes)
print("Waiting 150 seconds for window to flush...")
time.sleep(150)

# Step 4: Check aggregate (should show trade_count=50)
print("CHECK DATABASE: SELECT * FROM trade_aggregates WHERE symbol='TEST_CORRUPT'")
print("Expected: trade_count=50, vwap=100.00")
input("Press Enter after checking...")

# Step 5: Send late event
late_trade = {
    "trade_id": "LATE-001",
    "symbol": "TEST_CORRUPT",
    "price": "999.00",  # Different price to show corruption
    "volume": "10.00",
    "side": "BUY",
    "trader_id": "TESTER",
    "event_timestamp": (window_time + timedelta(seconds=30)).isoformat()
}
producer.produce('trades', key='TEST_CORRUPT', value=json.dumps(late_trade))
producer.flush()
print("Sent late event")

# Step 6: Wait and check again
time.sleep(150)
print("CHECK DATABASE AGAIN")
print("BUG: trade_count=1, vwap=999.00 (DATA CORRUPTED!)")
```

---

## 6.2 CRITICAL: Broken Audit Trail

### The Gap (VERIFIED)

**Evidence**:
- Table `raw_trades` EXISTS in [schema](sql/schema/001_create_trade_aggregates.sql#L44-L55)
- Consumer does NOT write to it (grep found 0 references in consumer code)

### Regulatory Risk

| Regulation | Requirement | Current State |
|------------|-------------|---------------|
| REMIT (EU) | Complete transaction records | NOT MET |
| MiFID II | Reconstruct any calculation | NOT MET |
| FERC (US) | 5-year trade retention | NOT MET |

### Detection

```sql
-- This should return data, currently returns 0
SELECT COUNT(*) FROM raw_trades;

-- This query is IMPOSSIBLE without raw_trades
SELECT
    r.trade_id,
    r.price,
    r.volume,
    a.vwap
FROM raw_trades r
JOIN trade_aggregates a
    ON r.symbol = a.symbol
    AND r.event_timestamp >= a.window_start
    AND r.event_timestamp < a.window_end;
```

### Fix Required

Add to [kafka_consumer.py](src/consumer/kafka_consumer.py) `_process_message`:
```python
# After parsing trade, before aggregation:
self._db_writer.write_raw_trade(
    trade=trade,
    kafka_partition=msg.partition(),
    kafka_offset=msg.offset(),
    received_at=datetime.now(UTC)
)
```

---

## 6.3 Idempotency Limitations

### When Idempotency Works

| Scenario | Works? | Why |
|----------|--------|-----|
| Consumer restart, replay same messages | YES | Same trades → same result |
| Duplicate Kafka delivery | YES | Same trade in window → same result |
| Late event within grace period | YES | Window state still in memory |

### When Idempotency Fails

| Scenario | Works? | Why |
|----------|--------|-----|
| Late event after window eviction | NO | Partial data overwrites complete data |
| Partial Kafka replay (data loss) | NO | Incomplete aggregate overwrites correct one |

---

# PART 7: RELIABILITY PATTERNS

## 7.1 Schema Evolution

### The Problem
Adding/removing fields can break producers or consumers.

### Current State
- JSON serialization (flexible but no schema enforcement)
- Pydantic validation on consumer

### Safe Changes

| Change | Safe? | Reason |
|--------|-------|--------|
| Add optional field with default | YES | Old messages work, new have default |
| Add required field | NO | Old messages fail validation |
| Remove field | NO | Consumers expecting it fail |
| Rename field | NO | Breaks everything |

### Test Schema Change

```python
# Current model
class TradeEvent(BaseModel):
    trade_id: str
    symbol: str
    price: Decimal
    # ... other fields

# SAFE: Add optional field
class TradeEventV2(BaseModel):
    trade_id: str
    symbol: str
    price: Decimal
    trade_venue: str | None = None  # Optional with default

# Test backward compatibility
old_message = {"trade_id": "123", "symbol": "POWER_DE", ...}  # No trade_venue
event = TradeEventV2(**old_message)  # Should work
assert event.trade_venue is None
```

### Production Recommendation
Use Avro/Protobuf with Schema Registry for enforced compatibility.

---

## 7.2 State Recovery

### Current Design

**Source**: [windowed_aggregator.py:83-86](src/consumer/windowed_aggregator.py#L83-L86)

```
- In-memory state (Python dict)
- No checkpointing to external store
- Recovery: Replay from last committed Kafka offset
```

### Recovery Time Calculation

```
Variables:
- Processing rate: ~1000 msg/sec
- Lag after 5-min downtime: 5 × 60 × 10 × 7 = 21,000 messages
- Recovery time: 21,000 / 1000 = 21 seconds
```

### Test Recovery

```bash
# 1. Kill consumer ungracefully
docker kill $(docker ps -q -f name=consumer)

# 2. Wait 2 minutes (lag builds)
sleep 120

# 3. Check lag
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator

# 4. Restart and time recovery
time docker-compose -f docker-compose-full.yml up -d consumer

# 5. Monitor until lag = 0
watch -n 5 'docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator 2>/dev/null | tail -1'
```

---

## 7.3 Backpressure Handling

### The Problem
During market volatility, trade volume spikes. Consumer can't keep up.

### Symptoms
- Consumer lag growing
- Memory pressure (many open windows)
- Stale dashboard data
- Potential OOM crash

### Detection

```bash
# Monitor lag growth rate
watch -n 10 'docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator'
```

### Solutions

| Solution | Trade-off |
|----------|-----------|
| Scale consumers (add instances) | Requires partition count >= consumer count |
| Increase batch size | Higher latency, better throughput |
| Optimize DB writes | Complexity |
| Drop low-priority data | Data loss |

### Alert Configuration

```yaml
# Prometheus alert rule
- alert: ConsumerLagCritical
  expr: kafka_consumer_lag > 50000
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Consumer lag is {{ $value }}"
```

---

# PART 8: API & INTEGRATION

## 8.1 API Overview

**File**: [api/main.py](src/api/main.py)

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/aggregates` | GET | Query aggregates (paginated) |
| `/api/v1/vwap` | GET | Current VWAP by symbol |
| `/ws/trades` | WebSocket | Real-time trade stream |

## 8.2 Rate Limiting (NOT IMPLEMENTED)

**Current State**: No rate limiting. Dashboard refreshing every second could overload DB.

**Recommended Fix**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/aggregates")
@limiter.limit("60/minute")
async def get_aggregates(...):
    ...
```

## 8.3 Caching (NOT IMPLEMENTED)

**Recommended**:
```python
import redis
from functools import wraps

redis_client = redis.Redis(host='redis', port=6379)

def cache_response(ttl_seconds=30):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(kwargs))}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl_seconds, json.dumps(result))
            return result
        return wrapper
    return decorator
```

---

# PART 9: TESTING & VALIDATION

## 9.1 Problem Framing Framework

For every issue, ask IN ORDER:

| # | Question | Purpose |
|---|----------|---------|
| 1 | **Why** does this happen? | Root cause |
| 2 | **What** is the impact? | Business/regulatory |
| 3 | **How** do we detect it? | Monitoring |
| 4 | **How** do we prevent it? | Design |
| 5 | **How** do we fix it? | Resolution |
| 6 | **How** do we prove it's fixed? | Validation |

## 9.2 Test Matrix

| # | Area | Test | Expected | Actual | Status |
|---|------|------|----------|--------|--------|
| 1 | Late Events | Event 5 min after window | Handled correctly | Creates new window, corrupts | **BUG** |
| 2 | Audit Trail | raw_trades populated | Yes | Empty | **GAP** |
| 3 | Idempotency (replay) | Reset offset, replay | Same result | Same result | OK |
| 4 | Idempotency (late) | Late after eviction | Correct update | Overwrites partial | **BUG** |
| 5 | Recovery | Kill consumer, restart | Catches up | Catches up | OK |
| 6 | VWAP | Manual calculation | Matches | Matches | OK |
| 7 | DLQ | Send malformed | Goes to DLQ | Goes to DLQ | OK |
| 8 | Graceful shutdown | SIGTERM | Flushes windows | Flushes | OK |
| 9 | Compression | Check chunks | Compressed | Configured | OK |

## 9.3 Data Validation Queries

**Data Freshness**:
```sql
SELECT
    NOW() - MAX(window_start) AS data_age,
    CASE
        WHEN NOW() - MAX(window_start) < INTERVAL '2 minutes' THEN 'HEALTHY'
        ELSE 'STALE'
    END AS status
FROM trade_aggregates;
```

**Gap Detection**:
```sql
WITH time_spine AS (
    SELECT generate_series(
        (SELECT MIN(window_start) FROM trade_aggregates WHERE window_start > NOW() - INTERVAL '1 hour'),
        (SELECT MAX(window_start) FROM trade_aggregates),
        INTERVAL '1 minute'
    ) AS expected_window
),
symbols AS (
    SELECT DISTINCT symbol FROM trade_aggregates LIMIT 7
),
expected AS (
    SELECT t.expected_window, s.symbol
    FROM time_spine t CROSS JOIN symbols s
),
actual AS (
    SELECT DISTINCT window_start, symbol FROM trade_aggregates
    WHERE window_start > NOW() - INTERVAL '1 hour'
)
SELECT COUNT(*) AS missing_windows
FROM expected e
LEFT JOIN actual a ON e.expected_window = a.window_start AND e.symbol = a.symbol
WHERE a.window_start IS NULL;
```

**Duplicate Check**:
```sql
SELECT symbol, window_start, COUNT(*)
FROM trade_aggregates
GROUP BY symbol, window_start
HAVING COUNT(*) > 1;
-- Should return 0 rows
```

**VWAP Sanity Check**:
```sql
SELECT
    symbol,
    MIN(vwap) AS min_vwap,
    AVG(vwap) AS avg_vwap,
    MAX(vwap) AS max_vwap,
    STDDEV(vwap) AS vwap_stddev
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY symbol;
-- Check for outliers (unusually low/high values)
```

---

# PART 10: CHAOS TESTING FRAMEWORK

## 10.1 Overview

The project includes a custom-built chaos testing framework for validating pipeline resilience. Located in `scripts/chaos/`.

**Key Files**:
| File | Purpose |
|------|---------|
| [run_chaos_tests.py](scripts/chaos/run_chaos_tests.py) | Main test orchestrator |
| [dlq_tool.py](scripts/chaos/dlq_tool.py) | DLQ inspection and management |
| [streaming/issues.py](scripts/chaos/streaming/issues.py) | 8 streaming chaos scenarios |
| [batch/issues.py](scripts/chaos/batch/issues.py) | 9 batch file chaos scenarios |
| [utils/dlq_inspector.py](scripts/chaos/utils/dlq_inspector.py) | DLQ analysis utilities |
| [utils/report.py](scripts/chaos/utils/report.py) | Test report generation |

## 10.2 Streaming Chaos Scenarios (8 Types)

| # | Issue Type | Description | Expected Behavior | Goes to DLQ? |
|---|------------|-------------|-------------------|--------------|
| 1 | **Poison Pill** | Invalid JSON (truncated, binary, partial) | JSONDecodeError, reject message | YES |
| 2 | **Schema Violation** | Valid JSON, wrong structure (missing field, wrong type) | ValidationError | YES |
| 3 | **Null Fields** | Required fields set to null | ValidationError | YES |
| 4 | **Encoding Issues** | Non-UTF8 data (latin1, invalid bytes) | UnicodeDecodeError | YES |
| 5 | **Duplicate Events** | Same trade_id sent multiple times | Idempotent handling | NO |
| 6 | **Late Events** | Event timestamp 2+ minutes old | Tests grace period | NO |
| 7 | **Out-of-Order Events** | Events arriving non-chronologically | Tests watermark handling | NO |
| 8 | **High Volume Burst** | 1000+ events at once | Tests backpressure | NO |

### Poison Pill Variants
```python
# From streaming/issues.py - 4 variants
"truncated"     # '{"trade_id": "123", "symbol": "AAPL", "pri'
"binary"        # Random bytes: bytes([0x00, 0xff, ...])
"partial_json"  # '{"trade_id": "123", "price": 150.0'  (missing braces)
"text"          # "This is not JSON at all!"
```

### Schema Violation Variants
```python
"missing_field"    # Required field removed (price, volume, etc.)
"wrong_type"       # price: [100, 200] instead of number
"invalid_enum"     # side: "HOLD" instead of BUY/SELL
"empty_string"     # symbol: ""
"negative_volume"  # volume: "-10.0"
"invalid_symbol"   # symbol: "invalid-symbol!"
```

## 10.3 Batch Chaos Scenarios (9 Types)

| # | Issue Type | Description | Expected Behavior | Should Fail? |
|---|------------|-------------|-------------------|--------------|
| 1 | **Corrupt File** | Truncated, binary garbage, null bytes | Parsing error | YES |
| 2 | **Schema Drift** | Missing columns, extra columns, renamed | Schema error | DEPENDS |
| 3 | **Encoding Issue** | Latin1, CP1252, UTF-16 instead of UTF-8 | UnicodeDecodeError | YES |
| 4 | **Empty File** | Zero bytes, header-only, whitespace | Graceful skip | NO |
| 5 | **Partial File** | Complete rows + incomplete last row | Row parsing error | YES |
| 6 | **Duplicate File** | Same content processed twice | Idempotent handling | NO |
| 7 | **Large File** | 100K+ rows | Performance test | NO |
| 8 | **Wrong Format** | JSON content with .csv extension | Format error | YES |
| 9 | **Malformed Rows** | Mix of valid and invalid rows | Partial failure | YES |

## 10.4 Running Chaos Tests

### Quick Start
```bash
cd JanAndFeb

# Run all chaos tests
python scripts/chaos/run_chaos_tests.py

# Run streaming tests only
python scripts/chaos/run_chaos_tests.py --streaming

# Run batch tests only
python scripts/chaos/run_chaos_tests.py --batch

# Quick subset test
python scripts/chaos/run_chaos_tests.py --quick

# Export detailed report
python scripts/chaos/run_chaos_tests.py --output report.json --detailed

# Export markdown report
python scripts/chaos/run_chaos_tests.py --output report.md
```

### Configuration Options
```bash
python scripts/chaos/run_chaos_tests.py \
  --bootstrap-servers localhost:9092 \
  --topic trades \
  --dlq-topic trades-dlq \
  --input-dir ./data/imports \
  --output chaos_report.json \
  --detailed
```

## 10.5 DLQ Management Tool

### Inspect DLQ
```bash
# View DLQ summary
python scripts/chaos/dlq_tool.py inspect

# View detailed entries
python scripts/chaos/dlq_tool.py inspect --detailed

# Filter by error type
python scripts/chaos/dlq_tool.py inspect --error-type ValidationError

# Limit entries
python scripts/chaos/dlq_tool.py inspect --limit 50
```

### Export DLQ
```bash
# Export all entries to JSON
python scripts/chaos/dlq_tool.py export dlq_entries.json
```

### Replay Fixed Messages
```bash
# Replay a fixed message back to main topic
python scripts/chaos/dlq_tool.py replay --file fixed_message.json
```

### Clear DLQ (Testing Only)
```bash
# Clear all DLQ messages (requires confirmation)
python scripts/chaos/dlq_tool.py clear --confirm
```

### Count Messages
```bash
# Count messages in topics
python scripts/chaos/dlq_tool.py count
```

## 10.6 Test Validation Workflow

### Step 1: Start Infrastructure
```bash
docker-compose -f docker-compose-full.yml up -d
```

### Step 2: Run Chaos Tests
```bash
python scripts/chaos/run_chaos_tests.py --streaming
```

### Step 3: Inspect Results
```bash
# Check DLQ for expected errors
python scripts/chaos/dlq_tool.py inspect --detailed

# Verify error types match expectations
python scripts/chaos/dlq_tool.py inspect --error-type JSONDecodeError
python scripts/chaos/dlq_tool.py inspect --error-type ValidationError
```

### Step 4: Validate Idempotency
```bash
# Check for duplicates in database
docker exec postgres psql -U trading -d trades -c "
SELECT symbol, window_start, COUNT(*)
FROM trade_aggregates
WHERE symbol LIKE '%TEST%'
GROUP BY symbol, window_start
HAVING COUNT(*) > 1;
"
```

### Step 5: Generate Report
```bash
python scripts/chaos/run_chaos_tests.py --output chaos_report.md
```

## 10.7 Expected Test Results

| Test Category | Expected Pass | Expected Fail | Notes |
|---------------|---------------|---------------|-------|
| Poison Pills | 0 | 10 | All should go to DLQ |
| Schema Violations | 0 | 10 | All should go to DLQ |
| Null Fields | 0 | 5 | All should go to DLQ |
| Encoding Issues | 0 | 5 | All should go to DLQ |
| Duplicates | 3 | 0 | Should be handled idempotently |
| Late Events | 5 | 0 | Should be processed (but may corrupt - see Part 6) |
| Out-of-Order | 10 | 0 | Should be handled by watermark |
| High Volume | 100+ | 0 | Should handle backpressure |

## 10.8 Chaos Test Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Chaos Test Runner                            │
│                  (run_chaos_tests.py)                           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────────┐           ┌───────────────────┐
│ Streaming Chaos   │           │   Batch Chaos     │
│ (simulator.py)    │           │  (simulator.py)   │
└────────┬──────────┘           └────────┬──────────┘
         │                               │
         ▼                               ▼
┌───────────────────┐           ┌───────────────────┐
│  Issue Generators │           │  Issue Generators │
│  (issues.py)      │           │  (issues.py)      │
│  - Poison Pills   │           │  - Corrupt Files  │
│  - Schema Errors  │           │  - Schema Drift   │
│  - Late Events    │           │  - Empty Files    │
│  - Duplicates     │           │  - Large Files    │
└────────┬──────────┘           └────────┬──────────┘
         │                               │
         ▼                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Kafka Topic                              │
│                        "trades"                                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Consumer Service                            │
│                  (validates, processes)                         │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────────┐           ┌───────────────────┐
│   DLQ Topic       │           │   PostgreSQL      │
│  "trades-dlq"     │           │  trade_aggregates │
│  (bad messages)   │           │  (valid messages) │
└────────┬──────────┘           └───────────────────┘
         │
         ▼
┌───────────────────┐
│  DLQ Inspector    │
│  (dlq_tool.py)    │
│  - Analyze errors │
│  - Export/replay  │
└───────────────────┘
```

---

# PART 11: FAILURE SCENARIOS & RUNBOOKS

## 11.1 Documented Failure Scenarios

**Source**: [docs/FAILURE_SCENARIOS.md](docs/FAILURE_SCENARIOS.md)

### Scenario 1: Consumer Pod Killed Mid-Processing

| Phase | State Before Kill | Recovery Behavior |
|-------|-------------------|-------------------|
| Parsing message | Offset not committed | Replay from last committed |
| Computing aggregates | Offset not committed | Replay, recompute |
| Writing to DB | Offset not committed | Replay, upsert handles duplicate |
| After DB write, before commit | Offset not committed | Replay, upsert handles duplicate |
| After commit | Offset committed | Resume from next message |

**Recovery Timeline**:
```
T+0s     Pod killed
T+10s    Consumer group rebalance triggered
T+30s    Partitions reassigned to surviving consumers
T+45s    Processing resumes
T+60s    Caught up
```

**Risk**: None (idempotent upserts prevent data loss/duplication)

### Scenario 2: PostgreSQL Unavailable (5 Minutes)

**Behavior**:
```
Consumer attempts DB write
        ↓
Write fails (connection error)
        ↓
Retry with exponential backoff (1s → 2s → 4s → 8s → 16s → 32s)
        ↓
Consumer blocks, offset not committed
        ↓
Kafka continues buffering messages
        ↓
DB recovers → writes resume → catch up
```

**Recovery Timeline**:
```
T+0m     PostgreSQL unavailable
T+1m     Consumer lag: ~600 messages
T+5m     Consumer lag: ~3000 messages
T+5m     PostgreSQL recovers
T+7m     Caught up (depends on consumer count)
```

**Key Metrics**:
- `db_write_errors` - Spikes immediately
- `kafka_consumer_lag` - Grows linearly
- `db_connection_pool_available` - Drops to zero

### Scenario 3: Kafka Broker Restarted

**Single Broker Restart**:
```
T+0s     Broker shutdown
T+5s     Leader election for affected partitions
T+10s    New leaders ready
T+15s    Producers discover new leaders
T+30s    Normal operation resumed
```

**Risk**: None with replication factor = 3 and acks=all

### Scenario 4: Network Partition (Consumer ↔ Kafka)

**Behavior**:
```
T+0s      Network partition begins
T+15s     Consumer heartbeat fails
T+45s     Session timeout, consumer removed from group
T+60s     Rebalance complete, other consumers take over
T+120s    Network recovers
T+135s    Consumer rejoins, new rebalance
T+165s    Normal operation
```

## 11.2 Failure Mode Comparison

| Scenario | Data Loss | Duplication | Recovery Time | Trader Impact |
|----------|-----------|-------------|---------------|---------------|
| Consumer killed | None | None | 30-60s | Minimal |
| PostgreSQL down 5min | None | None | 5-7min | Stale dashboard |
| Kafka broker restart | None | Low | 10-30s | Minimal |
| Network partition | None | Low | 60-90s | Minimal |

## 11.3 Runbook: Consumer Pod Killed

```bash
# 1. Check consumer group status
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator

# 2. Verify rebalance completed (no "Pending" state)

# 3. Check lag is decreasing
watch -n 5 'docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator'

# 4. No action needed if other consumers healthy
```

## 11.4 Runbook: PostgreSQL Unavailable

```bash
# 1. Check PostgreSQL status
docker logs postgres --tail 50

# 2. Verify connection from consumer
docker exec consumer python -c "
import psycopg
conn = psycopg.connect('postgresql://trading:trading@postgres:5432/trades')
print('Connected!')
"

# 3. Monitor consumer lag
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator

# 4. After recovery, verify catch-up
watch -n 10 'docker exec postgres psql -U trading -d trades -c \
  "SELECT NOW() - MAX(window_start) AS lag FROM trade_aggregates"'
```

## 11.5 Runbook: Kafka Broker Restart

```bash
# 1. Check cluster health
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# 2. Verify under-replicated partitions = 0
docker exec kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe --under-replicated-partitions

# 3. Check producer/consumer metrics
curl -s http://localhost:8001/metrics | grep kafka
curl -s http://localhost:8002/metrics | grep kafka

# 4. No action needed if ISR maintained
```

## 11.6 Observability Gaps

| Gap | Mitigation |
|-----|------------|
| No alert for single consumer failure | Monitor consumer group size |
| DB outage not immediately visible | Alert on write error rate |
| Rebalance frequency not tracked | Monitor rebalance count |
| End-to-end latency not measured | Add timestamp at producer, measure at DB |

---

# PART 12: DESIGN PATTERNS

## 12.1 Patterns Used in This Codebase

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Strategy** | [streaming/issues.py](scripts/chaos/streaming/issues.py) | Each issue type is a strategy for generating specific problems |
| **Factory** | [streaming/issues.py:572-609](scripts/chaos/streaming/issues.py#L572-L609) | `STREAMING_ISSUES` registry + `create_issue()` factory function |
| **Template Method** | [StreamingIssue.generate_batch()](scripts/chaos/streaming/issues.py#L68-L77) | Base class defines algorithm, subclasses override steps |
| **Protocol/Interface** | [IssueGenerator Protocol](scripts/chaos/streaming/issues.py#L36-L40) | Interface segregation for issue generators |
| **DTO (Data Transfer Object)** | [IssueResult dataclass](scripts/chaos/streaming/issues.py#L23-L33) | Immutable container for issue generation results |
| **Upsert/Idempotency** | [db_writer.py:31-48](src/consumer/db_writer.py#L31-L48) | INSERT ON CONFLICT for at-least-once delivery |
| **Circuit Breaker** | [resilience/circuit_breaker.py](src/ingestion/resilience/circuit_breaker.py) | Prevent cascading failures (CLOSED→OPEN→HALF_OPEN) |
| **Retry with Backoff** | [resilience/retry.py](src/ingestion/resilience/retry.py) | Automatic retry with exponential delay |
| **Rate Limiter** | [resilience/rate_limiter.py](src/ingestion/resilience/rate_limiter.py) | Control request throughput |
| **Decorator** | [retry.py:186-213](src/ingestion/resilience/retry.py#L186-L213) | `@retry_decorator` wraps functions with retry logic |
| **Context Manager** | [retry.py:216-290](src/ingestion/resilience/retry.py#L216-L290) | `async with RetryContext()` for manual retry control |
| **State Machine** | [circuit_breaker.py:24-29](src/ingestion/resilience/circuit_breaker.py#L24-L29) | Circuit states: CLOSED→OPEN→HALF_OPEN→CLOSED |

## 12.2 Strategy Pattern Deep Dive

**Problem**: Need to generate different types of problematic messages (poison pills, schema errors, etc.) with a unified interface.

**Solution**: Each issue type is a concrete strategy implementing `StreamingIssue`.

```python
# Base strategy (abstract)
class StreamingIssue(ABC):
    @abstractmethod
    def generate(self) -> IssueResult:
        """Each subclass implements its own generation logic."""
        pass

# Concrete strategies
class PoisonPillIssue(StreamingIssue):
    def generate(self) -> IssueResult:
        # Generate malformed JSON
        return IssueResult(issue_type="poison_pill", ...)

class SchemaViolationIssue(StreamingIssue):
    def generate(self) -> IssueResult:
        # Generate valid JSON with wrong schema
        return IssueResult(issue_type="schema_violation", ...)
```

**Usage**:
```python
# Strategy selection at runtime
strategies = [PoisonPillIssue(), SchemaViolationIssue(), LateEventIssue()]
for strategy in strategies:
    result = strategy.generate()  # Polymorphic call
    producer.send(result.message_bytes)
```

## 12.3 Factory Pattern Deep Dive

**Problem**: Create issue instances by name without knowing the concrete class.

**Solution**: Registry dictionary + factory function.

```python
# Registry (maps names to classes)
STREAMING_ISSUES: dict[str, type[StreamingIssue]] = {
    "poison_pill": PoisonPillIssue,
    "schema_violation": SchemaViolationIssue,
    "late_event": LateEventIssue,
    # ... more issues
}

# Factory function
def create_issue(name: str, **kwargs) -> StreamingIssue:
    if name not in STREAMING_ISSUES:
        raise ValueError(f"Unknown issue: {name}")
    return STREAMING_ISSUES[name](**kwargs)

# Usage
issue = create_issue("poison_pill", variant="truncated")
result = issue.generate()
```

**Why This Matters**:
- Decouples issue creation from usage
- Easy to add new issue types (just add to registry)
- Enables configuration-driven testing

## 12.4 Template Method Pattern Deep Dive

**Problem**: Generate batches of issues with consistent logic, but different individual generation.

**Solution**: Base class defines the template, subclasses override the variable part.

```python
class StreamingIssue(ABC):
    @abstractmethod
    def generate(self) -> IssueResult:
        """Variable part - subclasses implement this."""
        pass

    def generate_batch(self, count: int = 10) -> list[IssueResult]:
        """Template method - fixed algorithm using generate()."""
        return [self.generate() for _ in range(count)]

# Subclass only overrides generate(), gets batch for free
class PoisonPillIssue(StreamingIssue):
    def generate(self) -> IssueResult:
        return IssueResult(...)  # Just implement this one method
```

## 12.5 Circuit Breaker Pattern Deep Dive

**Problem**: External service failures can cascade, causing entire system to hang or crash.

**Solution**: Track failures, "open" the circuit to reject requests, then test recovery.

**States**:
```
CLOSED ──(failures >= threshold)──▶ OPEN
   ▲                                   │
   │                          (timeout elapsed)
   │                                   ▼
   └───(successes >= threshold)─── HALF_OPEN
                                       │
                                (failure)
                                   │
                                   ▼
                                 OPEN
```

**Code** (from [circuit_breaker.py](src/ingestion/resilience/circuit_breaker.py)):
```python
class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,      # Open after 5 failures
        recovery_timeout_seconds: int = 30,  # Wait 30s before testing
        half_open_max_calls: int = 3,    # 3 successes to close
    ):
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    async def call(self, func, *args, **kwargs):
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(self.name, self._get_remaining_timeout())

        try:
            result = await func(*args, **kwargs)
            self._on_success()  # May close circuit
            return result
        except Exception as e:
            self._on_failure(e)  # May open circuit
            raise

# Usage
cb = CircuitBreaker("finnhub", failure_threshold=5)
result = await cb.call(fetch_from_finnhub)

# Or as context manager
async with cb:
    await fetch_from_finnhub()
```

**Why This Matters**:
- Prevents system overload when external service is down
- Fails fast instead of waiting for timeout
- Automatically tests recovery

## 12.6 Retry with Exponential Backoff Deep Dive

**Problem**: Transient failures (network blips, temporary overload) need retry, but naive retry causes thundering herd.

**Solution**: Exponential backoff with jitter.

**Delay Calculation**:
```
delay = base_delay × (exponential_base ^ attempt)
delay = min(delay, max_delay)  # Cap at maximum
delay += random(-jitter, +jitter)  # Add randomness
```

**Code** (from [retry.py](src/ingestion/resilience/retry.py)):
```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 1.0      # Start with 1 second
    max_delay: float = 60.0      # Cap at 60 seconds
    exponential_base: float = 2.0  # Double each time
    jitter: bool = True          # Add randomness

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        return delay

# Delay sequence: 1s → 2s → 4s → 8s → 16s → 32s → 60s (capped)

# Usage as function
policy = RetryPolicy(max_retries=5, base_delay=1.0)
result = await retry_with_backoff(fetch_data, policy=policy)

# Usage as decorator
@retry_decorator(policy=RetryPolicy(max_retries=3))
async def fetch_data():
    return await api_call()
```

**Why Jitter Matters**:
- Without jitter: All clients retry at same time → thundering herd
- With jitter: Retries spread out → smoother load

## 12.7 Idempotent Upsert Pattern Deep Dive

**Problem**: At-least-once delivery means duplicates are possible. How to handle?

**Solution**: INSERT ON CONFLICT DO UPDATE (upsert).

```sql
-- The pattern (from db_writer.py)
INSERT INTO trade_aggregates (symbol, window_start, vwap, ...)
VALUES (%(symbol)s, %(window_start)s, %(vwap)s, ...)
ON CONFLICT (symbol, window_start) DO UPDATE SET
    vwap = EXCLUDED.vwap,           -- Replace with new value
    total_volume = EXCLUDED.total_volume,
    updated_at = NOW()
```

**Key Insight**: This REPLACES values, not accumulates. Works for:
- Consumer restart (replay same window → same result)
- Duplicate Kafka delivery (same trade → same aggregate)

**Fails for**:
- Late events after window eviction (partial data overwrites complete)

---

# PART 13: COMMON ISSUES & RESOLUTION GUIDE

## 13.1 Streaming Issues Summary

| Issue | Why It Happens | Detection | Resolution Code |
|-------|----------------|-----------|-----------------|
| **Poison Pill** | Truncated messages, binary corruption, encoding errors | `JSONDecodeError` in logs, DLQ count increases | See 13.2 |
| **Schema Violation** | Producer schema change, missing fields, wrong types | `ValidationError` in logs, DLQ count | See 13.3 |
| **Duplicate Events** | At-least-once delivery, producer retries, consumer restart | Compare trade_count vs expected | See 13.4 |
| **Late Events** | Network delays, producer batching, cross-DC replication | Events with old timestamps, corrupted aggregates | See 13.5 |
| **Consumer Lag** | Processing slower than ingestion, DB bottleneck | `kafka-consumer-groups --describe` shows growing lag | See 13.6 |
| **Rebalancing Storm** | Short session timeout, unstable consumers | Frequent "rebalance" in logs | See 13.7 |
| **Memory Pressure** | Too many open windows, large messages | OOMKilled pods, high memory metrics | See 13.8 |

## 13.2 Poison Pill Resolution

**Why**: Malformed JSON cannot be parsed → consumer crashes or blocks.

**Detection**:
```python
# In consumer logs
JSONDecodeError: Expecting property name: line 1 column 50
```

**Resolution Code**:
```python
# Wrap parsing in try/except, route to DLQ
def _process_message(self, msg: Message) -> None:
    try:
        trade = self._parse_message(msg)  # May raise JSONDecodeError
        # ... process normally
    except json.JSONDecodeError as e:
        # Route to Dead Letter Queue
        self._dlq_handler.handle_failed_message(
            raw_message=msg.value(),
            error=e,
            partition=msg.partition(),
            offset=msg.offset(),
        )
        # Commit offset to skip bad message
        self._consumer.commit(msg)
```

**Kafka DLQ Message Format**:
```json
{
  "original_message": "<raw bytes as string>",
  "error_type": "JSONDecodeError",
  "error_message": "Expecting property name: line 1 column 50",
  "failed_at": "2024-01-15T10:30:00Z",
  "partition": 2,
  "offset": 12345
}
```

## 13.3 Schema Violation Resolution

**Why**: Valid JSON but doesn't match expected schema (missing fields, wrong types).

**Detection**:
```python
# In consumer logs
ValidationError: 1 validation error for TradeEvent
price
  field required (type=value_error.missing)
```

**Resolution Code**:
```python
# Pydantic model with validation
class TradeEvent(BaseModel):
    trade_id: str
    symbol: str = Field(pattern=r"^[A-Z0-9_]+$")  # Regex validation
    price: Decimal = Field(gt=0)                   # Must be positive
    volume: Decimal = Field(gt=0)
    side: Literal["BUY", "SELL"]                   # Enum validation
    event_timestamp: datetime

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        if len(v) > 20:
            raise ValueError("Symbol too long")
        return v

# In consumer - same DLQ pattern as poison pill
except ValidationError as e:
    self._dlq_handler.handle_failed_message(...)
    self._consumer.commit(msg)
```

## 13.4 Duplicate Events Resolution

**Why**: At-least-once delivery guarantees duplicates are possible.

**Detection**:
```sql
-- Check for trade_id appearing multiple times (if stored)
SELECT trade_id, COUNT(*) FROM raw_trades
GROUP BY trade_id HAVING COUNT(*) > 1;
```

**Resolution Code**:
```sql
-- Idempotent upsert - duplicates overwrite with same value
INSERT INTO trade_aggregates (symbol, window_start, vwap, ...)
VALUES (...)
ON CONFLICT (symbol, window_start) DO UPDATE SET
    vwap = EXCLUDED.vwap,
    total_volume = EXCLUDED.total_volume,
    updated_at = NOW();
```

**Key**: Same input → same output. Duplicates are harmless.

## 13.5 Late Events Resolution

**Why**: Events arrive after their window has closed and been evicted.

**Detection**:
```sql
-- Find windows with suspiciously low trade counts
SELECT symbol, window_start, trade_count,
       updated_at - created_at AS time_since_creation
FROM trade_aggregates
WHERE trade_count < 5  -- Unusually low
  AND updated_at > created_at + INTERVAL '1 minute'
ORDER BY updated_at DESC;
```

**Current Behavior (BUG)**:
```python
# windowed_aggregator.py:156-169
if key not in self._windows:
    self._windows[key] = WindowState()  # NEW EMPTY window!
self._windows[key].add_trade(trade)     # Only late trade added
# Result: Partial aggregate overwrites correct one
```

**Resolution Code** (fix required):
```python
# Option 1: Check database before creating new window
def add_trade(self, trade: TradeEvent) -> list[TradeAggregate]:
    window_start = self._get_window_start(trade.event_timestamp)
    key = (trade.symbol, window_start)

    if key not in self._windows:
        # Check if window already flushed
        existing = self._db_writer.get_aggregate(trade.symbol, window_start)
        if existing:
            # Load existing state, add trade, write back
            state = WindowState.from_aggregate(existing)
            state.add_trade(trade)
            self._db_writer.write_aggregate(state.to_aggregate())
            return []  # Already written
        self._windows[key] = WindowState()

    self._windows[key].add_trade(trade)
    return self._flush_completed_windows()

# Option 2: Persist window state in Redis
def add_trade(self, trade: TradeEvent) -> list[TradeAggregate]:
    key = (trade.symbol, self._get_window_start(trade.event_timestamp))

    # Load from Redis if not in memory
    if key not in self._windows:
        cached = self._redis.get(f"window:{key}")
        if cached:
            self._windows[key] = WindowState.deserialize(cached)
        else:
            self._windows[key] = WindowState()

    self._windows[key].add_trade(trade)
    # Persist to Redis after each trade
    self._redis.set(f"window:{key}", self._windows[key].serialize())
    return self._flush_completed_windows()
```

## 13.6 Consumer Lag Resolution

**Why**: Processing slower than message arrival rate.

**Detection**:
```bash
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator

# Output shows LAG column growing
```

**Resolution Code**:
```python
# Option 1: Increase parallelism (more consumers)
# In docker-compose.yml
services:
  consumer:
    deploy:
      replicas: 3  # Match partition count

# Option 2: Batch database writes
def write_aggregates_batch(self, aggregates: list[TradeAggregate]) -> int:
    # Single transaction for multiple aggregates
    with self._get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(self.UPSERT_AGGREGATE_SQL, params_list)
        conn.commit()
    return len(aggregates)

# Option 3: Increase consumer batch size
consumer_config = {
    "fetch.min.bytes": 1024 * 1024,      # 1MB minimum fetch
    "fetch.max.wait.ms": 500,            # Wait up to 500ms
    "max.poll.records": 1000,            # More records per poll
}
```

## 13.7 Rebalancing Storm Resolution

**Why**: Consumers leaving/joining group triggers partition reassignment.

**Detection**:
```bash
# Frequent rebalance logs
grep -c "rebalance" consumer.log
# If > 10 per hour, there's a problem
```

**Resolution Code**:
```python
# Increase session timeout (consumer won't be evicted as quickly)
consumer_config = {
    "session.timeout.ms": 45000,        # 45 seconds (default 10s)
    "heartbeat.interval.ms": 15000,     # Heartbeat every 15s
    "max.poll.interval.ms": 300000,     # 5 min max between polls
}

# Use static group membership (Kafka 2.3+)
consumer_config = {
    "group.instance.id": f"consumer-{hostname}",  # Stable identity
}
```

## 13.8 Memory Pressure Resolution

**Why**: Too many open windows, large message accumulation.

**Detection**:
```bash
# Pod OOMKilled
kubectl describe pod consumer-xxx | grep -A5 "Last State"

# High memory metrics
curl http://localhost:8001/metrics | grep active_windows
```

**Resolution Code**:
```python
# Limit max windows (already implemented)
class WindowedAggregator:
    def __init__(self, max_windows: int = 1000):
        self.max_windows = max_windows

    def add_trade(self, trade: TradeEvent):
        if len(self._windows) > self.max_windows:
            self._evict_oldest_windows()  # Force flush oldest

# Set memory limits in Kubernetes
resources:
  limits:
    memory: "512Mi"
  requests:
    memory: "256Mi"
```

## 13.9 Batch File Issues Summary

| Issue | Why It Happens | Detection | Resolution |
|-------|----------------|-----------|------------|
| **Corrupt File** | Incomplete upload, disk error | CSV parsing error | Skip file, alert, retry later |
| **Schema Drift** | Upstream changes, version mismatch | Missing columns | Schema validation before processing |
| **Encoding Issue** | Legacy systems, cross-platform | UnicodeDecodeError | Try multiple encodings, use chardet |
| **Empty File** | Failed extraction, no data | Zero rows | Skip gracefully, no error |
| **Duplicate File** | Retry upload, backup copied | Same content hash | Idempotent processing, dedup by hash |

**Resolution Code for Encoding Detection**:
```python
import chardet

def detect_and_read(filepath: Path) -> str:
    raw_bytes = filepath.read_bytes()
    detected = chardet.detect(raw_bytes)
    encoding = detected["encoding"] or "utf-8"
    confidence = detected["confidence"]

    if confidence < 0.7:
        # Try common encodings
        for enc in ["utf-8", "latin-1", "cp1252", "utf-16"]:
            try:
                return raw_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode file: {filepath}")

    return raw_bytes.decode(encoding)
```

---

# PART 14: QUICK REFERENCE

## 12.1 Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Kafka UI | http://localhost:8080 | None |
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin / admin |
| Superset | http://localhost:8088 | admin / admin |
| API | http://localhost:8000 | None |
| API Docs | http://localhost:8000/docs | None |

## 12.2 Docker Commands

```bash
# Start basic stack
cd JanAndFeb
docker-compose up -d

# Start full analytics stack
docker-compose -f docker-compose-full.yml up -d

# View logs
docker-compose -f docker-compose-full.yml logs -f consumer producer

# Stop everything
docker-compose -f docker-compose-full.yml down

# Reset (destroy all data)
docker-compose -f docker-compose-full.yml down -v
```

## 12.3 Kafka Commands

```bash
# List topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe topic
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic trades

# Consumer lag
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group trade-aggregator

# Read messages
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic trades \
  --from-beginning \
  --max-messages 10

# Read DLQ
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic trades-dlq \
  --from-beginning

# Reset offset (CAREFUL!)
docker exec kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group trade-aggregator \
  --topic trades \
  --reset-offsets \
  --to-earliest \
  --dry-run
```

## 12.4 Database Commands

```bash
# Connect to database
docker exec -it postgres psql -U trading -d trades

# Quick queries
docker exec postgres psql -U trading -d trades -c "SELECT COUNT(*) FROM trade_aggregates"
docker exec postgres psql -U trading -d trades -c "SELECT * FROM trade_aggregates ORDER BY window_start DESC LIMIT 5"
```

## 12.5 Metrics Commands

```bash
# Consumer metrics
curl -s http://localhost:8001/metrics | grep -E "^(messages_processed|active_windows|dlq_messages)"

# Producer metrics
curl -s http://localhost:8002/metrics | grep -E "^(trades_produced)"

# Prometheus query
curl 'http://localhost:9090/api/v1/query?query=active_windows'
```

## 12.6 Key File Locations

| Category | Files |
|----------|-------|
| Configuration | `src/common/config.py` |
| Models | `src/common/models.py` |
| Producer | `src/producer/kafka_producer.py`, `trade_generator.py` |
| Consumer | `src/consumer/kafka_consumer.py`, `windowed_aggregator.py`, `db_writer.py` |
| Schema | `sql/schema/001_create_trade_aggregates.sql`, `003_timescaledb_setup.sql` |
| Docker | `docker-compose.yml`, `docker-compose-full.yml` |
| Monitoring | `monitoring/prometheus.yml`, `grafana/provisioning/` |
| **Chaos Testing** | `scripts/chaos/run_chaos_tests.py`, `scripts/chaos/dlq_tool.py` |
| **Streaming Issues** | `scripts/chaos/streaming/issues.py`, `simulator.py` |
| **Batch Issues** | `scripts/chaos/batch/issues.py`, `simulator.py` |
| **DLQ Utils** | `scripts/chaos/utils/dlq_inspector.py`, `kafka_helper.py`, `report.py` |
| **Failure Docs** | `docs/FAILURE_SCENARIOS.md` |

---

# STUDY SCHEDULE RECOMMENDATION

## Week 1: Foundations
| Day | Focus | Activities |
|-----|-------|------------|
| 1-2 | Kafka Basics | Run stack, inspect topics, understand partitions |
| 3-4 | Consumer Logic | Read windowed_aggregator.py, understand at-least-once |
| 5 | Test Bug | Run late event corruption test, verify bug exists |

## Week 2: Observability
| Day | Focus | Activities |
|-----|-------|------------|
| 1-2 | Prometheus | Write PromQL queries, understand metrics |
| 3-4 | Grafana | Build dashboard, create alerts |
| 5 | Integration | Connect all pieces, unified monitoring |

## Week 3: Analytics & Storage
| Day | Focus | Activities |
|-----|-------|------------|
| 1-2 | Superset | Create datasets, build charts |
| 3-4 | TimescaleDB | Understand chunks, compression, continuous aggregates |
| 5 | Performance | Run EXPLAIN ANALYZE, optimize queries |

## Week 4: Chaos Testing & Resilience
| Day | Focus | Activities |
|-----|-------|------------|
| 1-2 | Chaos Framework | Run `run_chaos_tests.py`, understand 17 scenarios |
| 3-4 | DLQ Management | Use `dlq_tool.py`, analyze failures, practice replay |
| 5 | Failure Scenarios | Simulate consumer kill, DB outage, Kafka restart |

## Week 5: Production Readiness
| Day | Focus | Activities |
|-----|-------|------------|
| 1-2 | Reliability | Test recovery, backpressure, schema evolution |
| 3-4 | Fix Bugs | Implement audit trail, fix late event handling |
| 5 | Documentation | Document learnings, create runbooks |

---

# SUMMARY

## Known Issues in This Codebase

| Issue | Severity | Status |
|-------|----------|--------|
| Late events corrupt data | CRITICAL | Unfixed |
| Audit trail not populated | CRITICAL | Unfixed |
| No API rate limiting | MEDIUM | Unfixed |
| No response caching | LOW | Unfixed |

## What Works Correctly

- Kafka producer/consumer communication
- At-least-once delivery with idempotent writes (for replay)
- VWAP calculation (NUMERIC precision)
- DLQ handling for malformed messages
- Graceful shutdown with window flush
- TimescaleDB compression and continuous aggregates
- Prometheus metrics exposure
- Basic Grafana/Superset integration
- **Chaos Testing Framework** (17 scenarios for streaming + batch)
- **DLQ Management Tools** (inspect, export, replay)
- **Failure Scenario Documentation** with runbooks

## Chaos Testing Coverage

| Category | Scenarios | Purpose |
|----------|-----------|---------|
| Streaming | 8 | Poison pills, schema errors, duplicates, late events |
| Batch | 9 | Corrupt files, schema drift, encoding, large files |
| Infrastructure | 4 | Consumer kill, DB outage, Kafka restart, network partition |

## Industry Best Practices Not Yet Implemented

1. Persistent window state (Redis/RocksDB)
2. Schema Registry (Avro/Protobuf)
3. Raw event storage for audit
4. Kafka transactions (exactly-once)
5. API rate limiting and caching

## Chaos Testing Commands Quick Reference

```bash
# Run all chaos tests
python scripts/chaos/run_chaos_tests.py

# Run streaming only
python scripts/chaos/run_chaos_tests.py --streaming

# Inspect DLQ
python scripts/chaos/dlq_tool.py inspect --detailed

# Export report
python scripts/chaos/run_chaos_tests.py --output report.md
```

This project is excellent for learning and includes a comprehensive chaos testing framework. However, the critical bugs in Part 6 must be fixed before production use in a regulated environment.
