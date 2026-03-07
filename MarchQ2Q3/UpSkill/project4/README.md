# Project 4: Real-Time Streaming Analytics

Multi-topic Kafka streaming platform with windowed aggregation, cross-topic anomaly detection,
WebSocket live dashboards, and Redis-backed state management.

## Architecture

```
Simulator -> Kafka (Redpanda) -> Consumers -> Redis (state) -> Postgres (serving)
                                     |
                                     v
                              FastAPI + WebSocket
```

### Topics
- `orders` -- order lifecycle events
- `clickstream` -- user click/page-view events
- `payments` -- payment status events
- `inventory` -- stock movement events

### Processing
- **Enrichment** -- join with customer/product reference data from Redis
- **Aggregation** -- tumbling (1m, 5m, 1h) and sliding windows in Redis
- **Anomaly Detection** -- cross-topic rules (spike orders, click floods, payment failures)
- **Flusher** -- periodic flush of completed windows to Postgres serving tables

## Quick Start

```bash
# Start infrastructure
docker-compose up -d

# Seed reference data
python -m simulation.seed

# Run simulator
python -m simulation.simulator --scenario normal --rate 50

# Run consumers (worker)
python -m src.main

# Run API
uvicorn src.api.main:app --port 8040 --reload
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/sales/realtime` | Real-time sales aggregates |
| GET | `/api/v1/products/performance` | Product performance metrics |
| GET | `/api/v1/customers/{id}/activity` | Customer activity timeline |
| GET | `/api/v1/anomalies` | Detected anomalies |
| GET | `/api/v1/topics` | Kafka topic info + lag |
| WS | `/api/v1/ws/sales` | Live sales stream |
| WS | `/api/v1/ws/events` | Live event stream |

## Configuration

All via environment variables -- see `.env.example`.

## Testing

```bash
pytest tests/unit -v --cov=src --cov-report=term-missing
```
