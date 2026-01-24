# Visualization & BI Integration Guide

This guide explains how to connect to the Energy Trading Platform for real-time visualization and business intelligence reporting.

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
