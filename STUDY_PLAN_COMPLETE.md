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
10. [Part 10: Quick Reference](#part-10-quick-reference)

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

**Files**: [kafka_producer.py](Jan/src/producer/kafka_producer.py), [trade_generator.py](Jan/src/producer/trade_generator.py)

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

**Configuration** (from [config.py](Jan/src/common/config.py)):
- Rate: 10 trades/sec (configurable)
- Burst: 5x multiplier, 30 sec duration, every 5 min
- Symbols: POWER_DE, POWER_FR, POWER_NL, GAS_NL, GAS_UK, BRENT_OIL, CARBON_EU

## 2.3 Consumer Deep Dive

**Files**: [kafka_consumer.py](Jan/src/consumer/kafka_consumer.py), [windowed_aggregator.py](Jan/src/consumer/windowed_aggregator.py)

**Processing Flow** (verified at [kafka_consumer.py:105-170](Jan/src/consumer/kafka_consumer.py#L105-L170)):

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

**File**: [windowed_aggregator.py](Jan/src/consumer/windowed_aggregator.py)

**Window Logic** (verified):
- **Type**: Tumbling windows (non-overlapping)
- **Duration**: 60 seconds (configurable)
- **Alignment**: Minute boundary (10:00:00, 10:01:00, etc.)
- **Grace Period**: 30 seconds for late events
- **Max Windows**: 1000 (prevents memory leak)

**VWAP Calculation** (verified at [windowed_aggregator.py:51-62](Jan/src/consumer/windowed_aggregator.py#L51-L62)):
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
cd Jan
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

**File**: [prometheus.yml](Jan/monitoring/prometheus.yml)

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

**Consumer Metrics** (from [metrics.py](Jan/src/consumer/metrics.py)):

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

**File**: [001_create_trade_aggregates.sql](Jan/sql/schema/001_create_trade_aggregates.sql)

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

**File**: [003_timescaledb_setup.sql](Jan/sql/schema/003_timescaledb_setup.sql)

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

**File**: [db_writer.py:31-48](Jan/src/consumer/db_writer.py#L31-L48)

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

**Source**: [windowed_aggregator.py:156-169](Jan/src/consumer/windowed_aggregator.py#L156-L169)

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
- Table `raw_trades` EXISTS in [schema](Jan/sql/schema/001_create_trade_aggregates.sql#L44-L55)
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

Add to [kafka_consumer.py](Jan/src/consumer/kafka_consumer.py) `_process_message`:
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

**Source**: [windowed_aggregator.py:83-86](Jan/src/consumer/windowed_aggregator.py#L83-L86)

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

**File**: [api/main.py](Jan/src/api/main.py)

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

# PART 10: QUICK REFERENCE

## 10.1 Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Kafka UI | http://localhost:8080 | None |
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin / admin |
| Superset | http://localhost:8088 | admin / admin |
| API | http://localhost:8000 | None |
| API Docs | http://localhost:8000/docs | None |

## 10.2 Docker Commands

```bash
# Start basic stack
cd Jan
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

## 10.3 Kafka Commands

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

## 10.4 Database Commands

```bash
# Connect to database
docker exec -it postgres psql -U trading -d trades

# Quick queries
docker exec postgres psql -U trading -d trades -c "SELECT COUNT(*) FROM trade_aggregates"
docker exec postgres psql -U trading -d trades -c "SELECT * FROM trade_aggregates ORDER BY window_start DESC LIMIT 5"
```

## 10.5 Metrics Commands

```bash
# Consumer metrics
curl -s http://localhost:8001/metrics | grep -E "^(messages_processed|active_windows|dlq_messages)"

# Producer metrics
curl -s http://localhost:8002/metrics | grep -E "^(trades_produced)"

# Prometheus query
curl 'http://localhost:9090/api/v1/query?query=active_windows'
```

## 10.6 Key File Locations

| Category | Files |
|----------|-------|
| Configuration | `Jan/src/common/config.py` |
| Models | `Jan/src/common/models.py` |
| Producer | `Jan/src/producer/kafka_producer.py`, `trade_generator.py` |
| Consumer | `Jan/src/consumer/kafka_consumer.py`, `windowed_aggregator.py`, `db_writer.py` |
| Schema | `Jan/sql/schema/001_create_trade_aggregates.sql`, `003_timescaledb_setup.sql` |
| Docker | `Jan/docker-compose.yml`, `docker-compose-full.yml` |
| Monitoring | `Jan/monitoring/prometheus.yml`, `grafana/provisioning/` |

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

## Week 4: Production Readiness
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

## Industry Best Practices Not Yet Implemented

1. Persistent window state (Redis/RocksDB)
2. Schema Registry (Avro/Protobuf)
3. Raw event storage for audit
4. Kafka transactions (exactly-once)
5. API rate limiting and caching

This project is excellent for learning but requires the fixes above before production use in a regulated environment.
