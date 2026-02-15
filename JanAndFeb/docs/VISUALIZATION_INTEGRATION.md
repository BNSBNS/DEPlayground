# Visualization & BI Integration Guide

This guide explains how to connect to the Energy Trading Platform for real-time visualization and business intelligence reporting.

---

## All Tools at a Glance

| Tool | URL | Login | Purpose |
|------|-----|-------|---------|
| **Grafana** | http://localhost:3000 | admin/admin | Time-series dashboards, Prometheus metrics |
| **Superset** | http://localhost:8088 | admin/admin | SQL analytics, business dashboards |
| **Kafka UI** | http://localhost:8080 | (none) | Kafka topic browser, message inspector |
| **Prometheus** | http://localhost:9090 | (none) | Raw metrics, PromQL queries |
| **API Docs** | http://localhost:8000/docs | (none) | Swagger UI, test endpoints |
| **Chat** | http://localhost:7860 | (none) | Natural language queries |

---

## Quick Start: Grafana

### What Grafana is For
- **Time-series visualization** of metrics (trades/sec, latency, lag)
- **Real-time dashboards** with auto-refresh
- **Alerting** based on metric thresholds
- **Data source**: Prometheus (metrics) + TimescaleDB (trade data)

### First Steps

1. Open http://localhost:3000
2. Login: `admin` / `admin`
3. Go to **Dashboards** → **New** → **New Dashboard**

### Create Your First Panel (Trades per Second)

1. Click **Add visualization**
2. Select **Prometheus** as data source
3. Enter query: `rate(trades_produced_total[1m])`
4. Set title: "Trades per Second"
5. Click **Apply**

### Essential Grafana Queries (Prometheus)

| What to See | PromQL Query |
|-------------|--------------|
| Trades produced/sec | `rate(trades_produced_total[1m])` |
| Messages processed/sec | `rate(messages_processed_total[1m])` |
| Kafka consumer lag | `kafka_consumer_lag_offsets` |
| Active windows | `active_windows` |
| Processing latency P95 | `histogram_quantile(0.95, rate(processing_duration_seconds_bucket[5m]))` |
| DB write latency P99 | `histogram_quantile(0.99, rate(db_write_duration_seconds_bucket[5m]))` |

### Create a Panel with Trade Data (TimescaleDB)

1. Click **Add visualization**
2. Select **TimescaleDB** as data source
3. Enter SQL:
```sql
SELECT
  $__timeGroup(window_start, '1m') as time,
  symbol,
  avg(vwap) as vwap
FROM trade_aggregates
WHERE $__timeFilter(window_start)
GROUP BY 1, symbol
ORDER BY 1
```
4. Set visualization to **Time series**
5. Click **Apply**

### Useful TimescaleDB Queries for Grafana

```sql
-- VWAP over time by symbol
SELECT
  $__timeGroup(window_start, '1m') as time,
  symbol,
  avg(vwap) as vwap
FROM trade_aggregates
WHERE $__timeFilter(window_start)
GROUP BY 1, symbol
ORDER BY 1

-- Volume over time
SELECT
  $__timeGroup(window_start, '5m') as time,
  symbol,
  sum(total_volume) as volume
FROM trade_aggregates
WHERE $__timeFilter(window_start)
GROUP BY 1, symbol
ORDER BY 1

-- Trade count heatmap
SELECT
  $__timeGroup(window_start, '1h') as time,
  symbol,
  sum(trade_count) as trades
FROM trade_aggregates
WHERE $__timeFilter(window_start)
GROUP BY 1, symbol
ORDER BY 1
```

### Recommended Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│  Row 1: Key Metrics (Single Stat panels)                       │
│  [Trades/sec] [Consumer Lag] [Active Windows] [DLQ Count]     │
├────────────────────────────────────────────────────────────────┤
│  Row 2: Throughput (Time series)                               │
│  [Producer Rate vs Consumer Rate over time]                   │
├────────────────────────────────────────────────────────────────┤
│  Row 3: VWAP by Symbol (Time series)                          │
│  [Line chart of VWAP per symbol]                              │
├────────────────────────────────────────────────────────────────┤
│  Row 4: Latency (Time series)                                 │
│  [Processing latency P50/P95/P99]                             │
└────────────────────────────────────────────────────────────────┘
```

---

## Quick Start: Superset

### What Superset is For
- **SQL exploration** via SQL Lab
- **Business dashboards** with charts and filters
- **Ad-hoc analysis** of trade aggregates
- **Data source**: TimescaleDB (trade_aggregates table)

### First Steps

1. Open http://localhost:8088
2. Login: `admin` / `admin`
3. If first time, run bootstrap:
   ```bash
   docker exec superset python /app/bootstrap_dashboards.py
   ```

### Using SQL Lab (Interactive SQL)

1. Go to **SQL** → **SQL Lab**
2. Select database: **trades**
3. Run queries against your data

### Essential SQL Lab Queries

```sql
-- Quick health check: Is data flowing?
SELECT COUNT(*), MAX(window_start) as latest
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '5 minutes';

-- VWAP by symbol (last hour)
SELECT
    symbol,
    ROUND(AVG(vwap)::numeric, 4) as avg_vwap,
    SUM(total_volume) as total_volume,
    SUM(trade_count) as trades
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY total_volume DESC;

-- Hourly volume trend
SELECT
    DATE_TRUNC('hour', window_start) as hour,
    symbol,
    SUM(total_volume) as volume
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Price volatility (spread analysis)
SELECT
    symbol,
    ROUND(MIN(min_price)::numeric, 4) as low,
    ROUND(MAX(max_price)::numeric, 4) as high,
    ROUND((MAX(max_price) - MIN(min_price))::numeric, 4) as spread
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY spread DESC;

-- DLQ errors (if any)
SELECT error_type, COUNT(*), MAX(failed_at)
FROM dlq_messages
GROUP BY error_type
ORDER BY COUNT(*) DESC;
```

### Creating Charts from SQL Lab

1. Run your query in SQL Lab
2. Click **Create Chart**
3. Choose visualization type:
   - **Line Chart**: For time series (VWAP over time)
   - **Bar Chart**: For comparisons (volume by symbol)
   - **Pie Chart**: For proportions (trade distribution)
   - **Table**: For detailed data
4. Configure axes and metrics
5. Click **Save** → Add to dashboard

### Pre-built Dashboard

After running the bootstrap script, access:
- **Dashboard**: http://localhost:8088/superset/dashboard/energy-trading/

This includes:
- VWAP by Symbol (line chart)
- Trading Volume (bar chart)
- Trade Distribution (pie chart)
- Volume Heatmap
- Top Movers (table)

---

## Quick Start: Kafka UI

### What Kafka UI is For
- **Browse topics** and see message counts
- **Inspect messages** in real-time
- **Monitor consumer groups** and lag
- **View broker health**

### First Steps

1. Open http://localhost:8080
2. No login required

### Key Pages to Check

| Page | What to Look For |
|------|------------------|
| **Topics** | `trades` (main), `trades-dlq` (errors), `trades-raw` |
| **Messages** | Click topic → Messages tab to see actual data |
| **Consumers** | Check `trade-aggregator` group lag |
| **Brokers** | Should show 1 healthy broker |

### Inspecting Messages

1. Click **Topics** → **trades**
2. Click **Messages** tab
3. You'll see live trade events in JSON:
```json
{
  "trade_id": "abc-123",
  "symbol": "AAPL",
  "price": "150.25",
  "volume": "100",
  "side": "BUY",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Checking Consumer Lag

1. Click **Consumers**
2. Find `trade-aggregator`
3. Check **Lag** column - should be low (< 100)

If lag is high:
- Consumer is behind
- Check consumer logs: `docker logs trade-consumer`

### Checking DLQ (Dead Letter Queue)

1. Click **Topics** → **trades-dlq**
2. Click **Messages**
3. Each message shows:
   - Original failed message
   - Error type and message
   - Timestamp of failure

---

## Quick Start: API & Swagger

### What the API is For
- **REST endpoints** for aggregates, VWAP, symbols
- **WebSocket** for real-time streaming
- **Swagger UI** for interactive testing

### First Steps

1. Open http://localhost:8000/docs
2. Interactive API documentation with "Try it out"

### Key Endpoints to Try

| Endpoint | Method | What it Returns |
|----------|--------|-----------------|
| `/health` | GET | Service health status |
| `/api/v1/symbols` | GET | List of trading symbols |
| `/api/v1/aggregates` | GET | Trade aggregates (paginated) |
| `/api/v1/aggregates/{symbol}` | GET | Aggregates for one symbol |
| `/api/v1/vwap` | GET | VWAP summary per symbol |

### Testing in Swagger UI

1. Click on an endpoint (e.g., `/api/v1/aggregates`)
2. Click **Try it out**
3. Set parameters (e.g., `hours=1`, `limit=10`)
4. Click **Execute**
5. See the response

### Quick cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# List symbols
curl http://localhost:8000/api/v1/symbols

# Get VWAP (last hour)
curl "http://localhost:8000/api/v1/vwap?hours=1"

# Get aggregates for AAPL (last 4 hours)
curl "http://localhost:8000/api/v1/aggregates/AAPL?hours=4&limit=50"
```

### WebSocket Streaming

Connect to real-time streams:

```javascript
// In browser console or Node.js
const ws = new WebSocket('ws://localhost:8000/ws/aggregates');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

Available WebSocket endpoints:
- `ws://localhost:8000/ws/trades` - All raw trades
- `ws://localhost:8000/ws/trades/{symbol}` - Trades for one symbol
- `ws://localhost:8000/ws/aggregates` - Completed VWAP aggregates

---

## Quick Start: Chat Interface

### What Chat is For
- **Natural language queries** about your data
- **Powered by Ollama** (local LLM)
- **Converts questions to SQL** automatically

### Prerequisites

Chat requires Ollama running locally:
```bash
# Install Ollama (if not installed)
# See: https://ollama.ai

# Pull model
ollama pull llama3.2

# Verify it's running
curl http://localhost:11434/api/tags
```

### First Steps

1. Open http://localhost:7860
2. Type questions in natural language

### Example Questions to Ask

```
"What's the total trading volume in the last hour?"

"Which symbol has the highest VWAP today?"

"Show me the top 5 symbols by trade count"

"What's the price range for AAPL in the last 24 hours?"

"Are there any errors in the DLQ?"

"How many trades happened per hour today?"
```

### How It Works

1. You type a question
2. LLM converts it to SQL
3. SQL runs against TimescaleDB
4. Results are formatted and returned

### Troubleshooting Chat

If chat doesn't respond:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check chat container logs
docker logs trade-chat

# Verify Ollama URL in .env
# OLLAMA_URL=http://host.docker.internal:11434
```

---

## Hands-On Experiments

These experiments help you understand the platform by doing. Run them in order.

### Experiment 1: Watch Data Flow End-to-End

**Goal:** See how a trade flows from producer → Kafka → consumer → database → API

```bash
# Terminal 1: Watch producer logs (generating trades)
docker logs -f trade-producer

# Terminal 2: Watch consumer logs (processing trades)
docker logs -f trade-consumer

# Terminal 3: Watch trades appear in Kafka UI
# Open http://localhost:8080 → Topics → trades → Messages

# Terminal 4: Query database to see aggregates
docker exec timescaledb psql -U trading -d trades -c \
  "SELECT symbol, window_start, vwap, trade_count FROM trade_aggregates ORDER BY window_start DESC LIMIT 5;"

# Terminal 5: Check API is serving the data
curl "http://localhost:8000/api/v1/vwap?hours=1" | jq
```

**What you learned:** The complete data pipeline from generation to API.

---

### Experiment 2: Understand Kafka Consumer Lag

**Goal:** See what happens when the consumer falls behind

```bash
# Step 1: Check current lag in Prometheus
# Open http://localhost:9090/graph
# Query: kafka_consumer_lag_offsets

# Step 2: Stop the consumer
docker stop trade-consumer

# Step 3: Watch lag increase in Prometheus
# Run the same query - lag should grow as producer keeps sending

# Step 4: Check Kafka UI
# Open http://localhost:8080 → Consumers → trade-aggregator
# Lag column shows messages waiting to be processed

# Step 5: Restart consumer and watch it catch up
docker start trade-consumer

# Step 6: Watch lag decrease in Prometheus
# Consumer processes backlog, lag returns to near-zero
```

**What you learned:** Consumer lag is real - if processing stops, messages queue up.

---

### Experiment 3: Inject a Bad Message (DLQ)

**Goal:** See how invalid data is handled

```bash
# Step 1: Inject invalid JSON (poison pill)
docker exec kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic trades <<< 'this is not valid JSON!'

# Step 2: Watch consumer logs for error
docker logs trade-consumer --tail 20

# Step 3: Check DLQ in Kafka UI
# Open http://localhost:8080 → Topics → trades-dlq → Messages
# You'll see the failed message with error details

# Step 4: Check DLQ in database
docker exec timescaledb psql -U trading -d trades -c \
  "SELECT error_type, error_message, failed_at FROM dlq_messages ORDER BY failed_at DESC LIMIT 5;"

# Step 5: Check DLQ metric in Prometheus
# Query: dlq_messages_total
```

**What you learned:** Invalid messages go to DLQ, not crash the pipeline.

---

### Experiment 4: Compare Prometheus vs Grafana

**Goal:** Understand when to use each

```bash
# PROMETHEUS: Ad-hoc queries
# Open http://localhost:9090/graph
# Query: rate(trades_produced_total[1m])
# Good for: Quick debugging, one-off questions

# GRAFANA: Persistent dashboards
# Open http://localhost:3000
# Create a dashboard with the same query
# Good for: Ongoing monitoring, team visibility

# Try this: Create a Grafana panel
# 1. New Dashboard → Add visualization
# 2. Data source: Prometheus
# 3. Query: rate(trades_produced_total[1m])
# 4. Save it
# Now you have a persistent view vs throwaway Prometheus queries
```

**What you learned:** Prometheus = ad-hoc queries, Grafana = persistent dashboards.

---

### Experiment 5: SQL Lab vs Pre-built Charts (Superset)

**Goal:** Understand exploratory vs operational analytics

```bash
# SQL LAB: Exploratory (you don't know what you're looking for)
# Open http://localhost:8088 → SQL → SQL Lab
# Try queries like:
SELECT symbol, COUNT(*) as trades, SUM(total_volume) as vol
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY vol DESC;

# PRE-BUILT CHARTS: Operational (you check the same thing daily)
# Go to Dashboards → Energy Trading Platform
# These are saved views you don't recreate each time

# Try this: Convert an SQL Lab query to a chart
# 1. Run your query in SQL Lab
# 2. Click "Create Chart"
# 3. Choose visualization type (Bar Chart)
# 4. Save to a dashboard
```

**What you learned:** SQL Lab for exploration, dashboards for routine monitoring.

---

### Experiment 6: Trace a Single Symbol

**Goal:** Follow one symbol through the entire system

```bash
# Pick a symbol (e.g., AAPL)

# 1. See it in Kafka messages
# Kafka UI → Topics → trades → Messages
# Search for "AAPL" in the message content

# 2. Query aggregates in Superset SQL Lab
SELECT * FROM trade_aggregates
WHERE symbol = 'AAPL'
ORDER BY window_start DESC
LIMIT 20;

# 3. Get it via API
curl "http://localhost:8000/api/v1/aggregates/AAPL?hours=1" | jq

# 4. Create a Grafana panel just for AAPL
# Query: rate(messages_processed_total{symbol="AAPL"}[1m])

# 5. Ask Chat about it
# Open http://localhost:7860
# "What's the VWAP for AAPL in the last hour?"
```

**What you learned:** Same data accessible via multiple interfaces.

---

### Experiment 7: Understand Window Aggregation

**Goal:** See how 1-minute windows work

```bash
# Step 1: Query raw vs aggregated
docker exec timescaledb psql -U trading -d trades -c "
  SELECT
    window_start,
    window_end,
    trade_count,
    vwap
  FROM trade_aggregates
  WHERE symbol = 'AAPL'
  ORDER BY window_start DESC
  LIMIT 5;
"

# Step 2: Watch a window close in Prometheus
# Query: active_windows
# This shows how many windows are currently being built

# Step 3: Watch aggregates_written increase
# Query: rate(aggregates_written_total[1m])
# Each bump = a window closed and was written to DB

# Step 4: Check window timing
# Notice window_start is always on the minute boundary (10:01:00, 10:02:00)
# Events within that minute are aggregated together
```

**What you learned:** Trades are grouped into 1-minute tumbling windows.

---

### Experiment 8: Stress Test with Burst Mode

**Goal:** See how the system handles load spikes

```bash
# Step 1: Check current throughput in Prometheus
# Query: rate(trades_produced_total[1m])
# Note the baseline rate (probably ~10/sec)

# Step 2: Check if burst mode is active
# Query: producer_burst_mode
# 0 = normal, 1 = burst

# Step 3: Wait for burst (happens every 5 minutes for 30 seconds)
# Or trigger manually by restarting producer near burst time

# Step 4: Watch metrics during burst
# - trades_produced_total rate should spike
# - kafka_consumer_lag_offsets might increase
# - active_windows might increase

# Step 5: See how quickly consumer catches up after burst
```

**What you learned:** System handles load spikes, temporary lag is normal.

---

### Experiment 9: Break and Fix Something

**Goal:** Practice troubleshooting

```bash
# Break: Stop the database
docker stop timescaledb

# Observe:
# - Consumer logs show connection errors
# - Prometheus: Check for error metrics
# - API: curl http://localhost:8000/health (should fail)

# Fix: Restart database
docker start timescaledb

# Observe recovery:
# - Consumer reconnects
# - Health returns to normal
# - Lag (if any) is processed
```

**What you learned:** Failure modes and recovery behavior.

---

### Quick Reference: What Tool for What Question?

| Question Type | Tool | Why |
|--------------|------|-----|
| "Is data flowing right now?" | Prometheus/Grafana | Real-time metrics |
| "What's in the Kafka topic?" | Kafka UI | Message inspection |
| "What does this symbol's data look like?" | Superset SQL Lab | Exploratory SQL |
| "Show me daily volume trends" | Superset Dashboard | Pre-built charts |
| "What was the VWAP at 3pm yesterday?" | API | Programmatic access |
| "Tell me about today's trading" | Chat | Natural language |

---

## Quick Start

### 1. Start the Full Stack

```bash
# Start everything (API, Kafka, TimescaleDB, Grafana, Superset)
docker-compose -f docker-compose-full.yml up -d

# Verify all services are running
docker-compose -f docker-compose-full.yml ps
```

### 2. Available Endpoints

Once running, you'll have access to:

| Service | URL | Purpose |
|---------|-----|---------|
| **REST API** | http://localhost:8000 | Data queries & API docs |
| **API Docs** | http://localhost:8000/docs | Swagger/OpenAPI |
| **WebSocket** | ws://localhost:8000/ws/* | Real-time streaming |
| **Grafana** | http://localhost:3000 | Monitoring dashboards |
| **Superset** | http://localhost:8088 | BI & analytics |
| **Kafka UI** | http://localhost:8080 | Kafka management |

---

## Web Frontend Integration

### Real-Time Data via WebSocket

Connect to WebSocket endpoints for live streaming data.

#### Available WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/ws/trades` | All raw trade events |
| `ws://localhost:8000/ws/trades/{symbol}` | Trades filtered by symbol (e.g., `POWER_DE`) |
| `ws://localhost:8000/ws/aggregates` | Completed 1-minute VWAP aggregates |

#### JavaScript Example

```javascript
// Connect to real-time aggregates stream
const ws = new WebSocket('ws://localhost:8000/ws/aggregates');

ws.onopen = () => {
  console.log('Connected to aggregates stream');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Handle heartbeat messages
  if (data.type === 'heartbeat') {
    console.log('Heartbeat received');
    return;
  }

  // Process aggregate data
  console.log('Aggregate:', {
    symbol: data.symbol,
    vwap: data.vwap,
    volume: data.total_volume,
    trades: data.trade_count
  });

  // Update your charts/UI here
  updateChart(data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected - reconnecting in 5s...');
  setTimeout(connectWebSocket, 5000);
};
```

#### Python Example

```python
import asyncio
import websockets
import json

async def stream_aggregates():
    uri = "ws://localhost:8000/ws/aggregates"

    async with websockets.connect(uri) as websocket:
        print("Connected to aggregates stream")

        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "heartbeat":
                continue

            print(f"Symbol: {data['symbol']}, VWAP: {data['vwap']}, Volume: {data['total_volume']}")

asyncio.run(stream_aggregates())
```

### REST API for Historical Data

Use REST endpoints for historical queries and dashboard refresh.

#### Available REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/aggregates` | GET | Paginated trade aggregates |
| `/api/v1/aggregates/{symbol}` | GET | Aggregates for specific symbol |
| `/api/v1/vwap` | GET | VWAP summary per symbol |
| `/api/v1/symbols` | GET | List all trading symbols |
| `/health` | GET | Health check |

#### Query Parameters

**GET /api/v1/aggregates**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | null | Filter by symbol |
| `hours` | int | 24 | Hours of historical data (1-168) |
| `limit` | int | 100 | Max results (1-1000) |
| `offset` | int | 0 | Pagination offset |

#### Example Requests

```bash
# Get last 24 hours of aggregates
curl http://localhost:8000/api/v1/aggregates

# Get POWER_DE aggregates for last 4 hours
curl "http://localhost:8000/api/v1/aggregates/POWER_DE?hours=4"

# Get VWAP summary for all symbols (last hour)
curl "http://localhost:8000/api/v1/vwap?hours=1"

# List available symbols
curl http://localhost:8000/api/v1/symbols
```

#### Response Format

```json
{
  "data": [
    {
      "symbol": "POWER_DE",
      "window_start": "2024-01-15T10:00:00Z",
      "window_end": "2024-01-15T10:01:00Z",
      "vwap": "45.12345678",
      "total_volume": "1250.50000000",
      "trade_count": 47,
      "max_price": "46.00000000",
      "min_price": "44.25000000"
    }
  ],
  "total": 1440,
  "limit": 100,
  "offset": 0
}
```

---

## PowerBI Integration

### Option 1: REST API Connector (Recommended for Scheduled Refresh)

1. Open PowerBI Desktop
2. **Get Data** > **Web**
3. Enter URL: `http://localhost:8000/api/v1/aggregates?hours=168&limit=1000`
4. Transform data as needed in Power Query Editor
5. Set up scheduled refresh

**Power Query M Code Example:**
```m
let
    Source = Json.Document(Web.Contents("http://localhost:8000/api/v1/aggregates?hours=168&limit=1000")),
    data = Source[data],
    #"Converted to Table" = Table.FromList(data, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    #"Expanded Column1" = Table.ExpandRecordColumn(#"Converted to Table", "Column1",
        {"symbol", "window_start", "window_end", "vwap", "total_volume", "trade_count", "max_price", "min_price"})
in
    #"Expanded Column1"
```

### Option 2: Direct PostgreSQL Connection (Recommended for Large Datasets)

1. Open PowerBI Desktop
2. **Get Data** > **PostgreSQL database**
3. Enter connection details:

| Setting | Value |
|---------|-------|
| Server | `localhost` |
| Port | `5432` |
| Database | `trades` |
| Username | `trading` |
| Password | `trading` |

4. Select the `trade_aggregates` table
5. Load or transform data

**Direct SQL Query:**
```sql
SELECT
    symbol,
    window_start,
    window_end,
    vwap,
    total_volume,
    trade_count,
    max_price,
    min_price
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '7 days'
ORDER BY window_start DESC
```

### Option 3: ODBC Connection

1. Install PostgreSQL ODBC driver
2. Create a DSN in ODBC Data Source Administrator:
   - Driver: PostgreSQL Unicode
   - Server: localhost
   - Port: 5432
   - Database: trades
   - User: trading
   - Password: trading
3. In PowerBI: **Get Data** > **ODBC** > Select your DSN

---

## Grafana Dashboards

Grafana is pre-configured with TimescaleDB as a datasource.

### Access Grafana

1. Open http://localhost:3000
2. Login: `admin` / `admin`

### Create a Dashboard

1. **Create** > **Dashboard** > **Add visualization**
2. Select **TimescaleDB** datasource
3. Use this example query:

```sql
SELECT
  $__timeGroup(window_start, '1m') as time,
  symbol,
  avg(vwap) as vwap,
  sum(total_volume) as volume
FROM trade_aggregates
WHERE $__timeFilter(window_start)
GROUP BY 1, symbol
ORDER BY 1
```

### Pre-built Panels

Create panels for:
- **VWAP Time Series**: Line chart of VWAP over time per symbol
- **Volume Heatmap**: Volume traded by symbol and time
- **Trade Count**: Bar chart of trade counts
- **Price Range**: Min/Max price bands

---

## Apache Superset

### Initial Setup (First Time Only)

After starting the stack, initialize Superset:

```bash
# Initialize database
docker exec superset superset db upgrade

# Create admin user
docker exec superset superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@local \
  --password admin

# Initialize Superset
docker exec superset superset init
```

### Connect to Database

1. Open http://localhost:8088
2. Login: `admin` / `admin`
3. **Settings** > **Database Connections** > **+ Database**
4. Select **PostgreSQL**
5. Enter connection string:
   ```
   postgresql://trading:trading@timescaledb:5432/trades
   ```
6. Test and save connection

### Create Charts

1. **SQL Lab** > **SQL Editor**
2. Run queries against `trade_aggregates` table
3. **Save** > **Save as Chart**

**Example Queries:**

```sql
-- VWAP by Symbol (Last Hour)
SELECT symbol,
       SUM(vwap * total_volume) / SUM(total_volume) as weighted_vwap,
       SUM(total_volume) as total_volume
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol;

-- Hourly Volume Trend
SELECT date_trunc('hour', window_start) as hour,
       symbol,
       SUM(total_volume) as volume
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY 1, 2
ORDER BY 1;
```

---

## Database Schema Reference

### trade_aggregates Table

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | VARCHAR(20) | Trading symbol (e.g., POWER_DE, GAS_NL) |
| `window_start` | TIMESTAMPTZ | Start of 1-minute window |
| `window_end` | TIMESTAMPTZ | End of 1-minute window |
| `vwap` | NUMERIC(18,8) | Volume-weighted average price |
| `total_volume` | NUMERIC(18,8) | Total volume in window |
| `trade_count` | INTEGER | Number of trades |
| `max_price` | NUMERIC(18,8) | Highest price in window |
| `min_price` | NUMERIC(18,8) | Lowest price in window |
| `lmp` | NUMERIC(18,8) | Locational Marginal Price (nullable) |
| `lmp_energy` | NUMERIC(18,8) | LMP energy component (nullable) |
| `lmp_congestion` | NUMERIC(18,8) | LMP congestion component (nullable) |
| `lmp_loss` | NUMERIC(18,8) | LMP loss component (nullable) |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

**Primary Key:** `(symbol, window_start)`

---

## Troubleshooting

### WebSocket Connection Issues

```bash
# Check API is running
curl http://localhost:8000/health

# Check Kafka connectivity
docker exec trade-api curl -s http://localhost:8000/ready
```

### No Data in Dashboards

```bash
# Verify producer is generating data
docker-compose -f docker-compose-full.yml logs -f producer

# Check consumer is writing to DB
docker-compose -f docker-compose-full.yml logs -f consumer

# Query database directly
docker exec timescaledb psql -U trading -d trades -c \
  "SELECT COUNT(*) FROM trade_aggregates;"
```

### PowerBI Connection Refused

- Ensure PostgreSQL port 5432 is exposed
- Check firewall settings
- For Docker on Windows/Mac, use `host.docker.internal` instead of `localhost`

---

## Architecture Overview

```
                                    ┌─────────────────┐
                                    │   Web Frontend  │
                                    │   (React, etc)  │
                                    └────────┬────────┘
                                             │ WebSocket
                                             ▼
┌──────────┐    ┌─────────┐    ┌─────────────────────────┐    ┌──────────────┐
│ Producer │───▶│  Kafka  │───▶│      FastAPI Server     │◀───│   PowerBI    │
└──────────┘    └────┬────┘    │  • REST API (8000)      │    │   Tableau    │
                     │         │  • WebSocket Streaming  │    │   etc.       │
                     │         └───────────┬─────────────┘    └──────────────┘
                     │                     │                          │
                     ▼                     ▼                          │
              ┌─────────────┐    ┌─────────────────┐                  │
              │  Consumer   │───▶│   TimescaleDB   │◀─────────────────┘
              │ (Aggregator)│    │   (PostgreSQL)  │         Direct SQL
              └─────────────┘    └────────┬────────┘
                                          │
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                         ┌────────┐  ┌────────┐  ┌──────────┐
                         │Grafana │  │Superset│  │Prometheus│
                         │ :3000  │  │ :8088  │  │  :9090   │
                         └────────┘  └────────┘  └──────────┘
```

---

## Summary

| Use Case | Recommended Approach |
|----------|---------------------|
| Real-time web dashboard | WebSocket `/ws/aggregates` |
| Historical data queries | REST API `/api/v1/aggregates` |
| PowerBI scheduled refresh | REST API or Direct PostgreSQL |
| Interactive BI | Apache Superset |
| System monitoring | Grafana + Prometheus |
