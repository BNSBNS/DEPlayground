# Energy Trading Platform

A production-grade real-time analytics platform for energy trading, featuring Kafka streaming, windowed aggregations, and PostgreSQL storage.

## Architecture Overview

```
┌──────────────┐     ┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│    Trade     │────▶│    Kafka    │────▶│    Streaming     │────▶│ PostgreSQL  │
│   Producer   │     │   Cluster   │     │    Consumer      │     │   (OLTP)    │
│              │     │             │     │                  │     │             │
│ • Generates  │     │ • trades    │     │ • 1-min windows  │     │ • Aggregates│
│   trade      │     │   topic     │     │ • VWAP calc      │     │ • Queries   │
│   events     │     │ • DLQ topic │     │ • DLQ handling   │     │ • Indexes   │
└──────────────┘     └─────────────┘     └──────────────────┘     └─────────────┘
```

## Features

- **Real-time Streaming**: Kafka-based trade event ingestion with at-least-once delivery
- **Windowed Aggregation**: 1-minute tumbling windows with VWAP, volume, and price metrics
- **Idempotent Processing**: `INSERT ... ON CONFLICT` ensures correctness during replays
- **Dead Letter Queue**: Malformed messages routed to DLQ for investigation
- **Production-Ready**: Docker, Kubernetes, CI/CD, monitoring documentation

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- (Optional) Conda for environment management
- (Optional) Kind for Kubernetes testing

### Option 1: Using Conda (Recommended)

```bash
# Create and activate conda environment
conda env create -f environment.yml
conda activate energy-trading

# Install project in editable mode
pip install -e ".[dev]"
```

### Option 2: Using pip/venv

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install project
pip install -e ".[dev]"
```

### Start Infrastructure

```bash
# Start Kafka, Zookeeper, and PostgreSQL
docker-compose up -d kafka postgres

# Wait for services to be healthy
docker-compose ps

# Initialize database schema
docker-compose exec postgres psql -U trading -d trades \
  -f /docker-entrypoint-initdb.d/001_create_trade_aggregates.sql
```

### Run Services

```bash
# Terminal 1: Start producer
python -m src.producer.main

# Terminal 2: Start consumer
python -m src.consumer.main
```

### Verify Data Flow

```bash
# Check aggregates in database
docker-compose exec postgres psql -U trading -d trades -c \
  "SELECT symbol, window_start, vwap, trade_count FROM trade_aggregates ORDER BY window_start DESC LIMIT 5;"
```

## Development

### Running Tests

```bash
# Run unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit -v --cov=src --cov-report=html

# Run integration tests (requires running infrastructure)
POSTGRES_DSN=postgresql://trading:trading@localhost:5432/trades pytest tests/integration -v
```

### Linting and Type Checking

```bash
# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/ --strict

# Format code
ruff format src/ tests/
```

### Full Stack with Docker Compose

```bash
# Build and run everything
docker-compose up --build

# View logs
docker-compose logs -f producer consumer

# Stop everything
docker-compose down
```

## Project Structure

```
Jan/
├── src/
│   ├── common/           # Shared modules (models, config, utils)
│   ├── producer/         # Trade event producer (Q3)
│   ├── consumer/         # Streaming consumer with DLQ (Q4, Q5)
│   └── analytics/        # Time-series processor (Q8)
├── sql/
│   ├── schema/           # Database DDL (Q6)
│   └── queries/          # Analytical queries (Q7)
├── docker/               # Dockerfiles (Q9)
├── k8s/                  # Kubernetes manifests (Q10)
├── scripts/              # CD simulation scripts (Q13)
├── docs/                 # Architecture and monitoring docs (Q1, Q2, Q11, Q14)
├── tests/                # Unit and integration tests
└── .github/workflows/    # CI pipeline (Q12)
```

## Key Design Decisions

### Streaming Semantics

- **At-least-once delivery** with manual offset commit after successful DB write
- **Idempotent upserts** via `INSERT ... ON CONFLICT DO UPDATE`
- **Event time** (not processing time) for window assignment

### Database Design

- **NUMERIC(18,8)** for price/volume precision (no floating point errors)
- **Composite PK** `(symbol, window_start)` enables idempotent writes
- **Time partitioning** for efficient range queries
- **BRIN indexes** optimized for time-series access patterns

### Configuration

All configuration via environment variables (12-factor app):

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | `localhost:9092` |
| `KAFKA_TOPIC` | Main trades topic | `trades` |
| `KAFKA_DLQ_TOPIC` | Dead Letter Queue topic | `trades-dlq` |
| `POSTGRES_DSN` | PostgreSQL connection string | (see .env.example) |
| `PRODUCER_RATE` | Events per second | `10` |
| `WINDOW_DURATION_SECONDS` | Aggregation window | `60` |

See [.env.example](.env.example) for complete configuration options.

## Documentation

### Core Concepts

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | End-to-end system design (Q1) |
| [STREAMING_SEMANTICS.md](docs/STREAMING_SEMANTICS.md) | Delivery guarantees, CAP/ACID, upsert patterns (Q2, Q5-6, Q8-10) |
| [FAILURE_SCENARIOS.md](docs/FAILURE_SCENARIOS.md) | Failure modes and recovery (Q11) |
| [MONITORING_STRATEGY.md](docs/MONITORING_STRATEGY.md) | Metrics and alerts (Q14) |

### Operations

| Document | Description |
|----------|-------------|
| [K8S_AUTOSCALING_HA.md](docs/K8S_AUTOSCALING_HA.md) | Autoscaling, HA, recovery validation (Q1) |
| [CDC_SCD_CACHING.md](docs/CDC_SCD_CACHING.md) | CDC, SCD, caching strategies (Q4, Q7) |

### SQL Queries

| Query | Description |
|-------|-------------|
| [vwap_last_60_minutes.sql](sql/queries/vwap_last_60_minutes.sql) | VWAP per symbol (Q7) |
| [data_freshness_check.sql](sql/queries/data_freshness_check.sql) | Data freshness validation (Q3) |

### Monitoring Stack

| File | Description |
|------|-------------|
| [k8s/monitoring/](k8s/monitoring/) | Prometheus + Grafana stack (Q1a, Q2) |
| [src/common/metrics.py](src/common/metrics.py) | Prometheus metrics implementation (Q2) |

## Kubernetes Deployment

```bash
# Create Kind cluster
./scripts/setup-kind.sh

# Build and load images
./scripts/local-cd.sh

# Deploy
kubectl apply -f k8s/

# Check status
kubectl get pods -n trading
```

See [k8s/](k8s/) for deployment manifests including:
- Resource requests/limits (Guaranteed QoS)
- Liveness and readiness probes
- HPA for auto-scaling based on consumer lag

## Trade-offs and Assumptions

### Trade-offs

| Decision | Trade-off |
|----------|-----------|
| In-memory windows | Simplicity over durability (state lost on crash, recovered via replay) |
| PostgreSQL (not OLAP) | Easier operations vs. sub-second queries on large datasets |
| At-least-once + idempotency | Simpler than true exactly-once transactions |

### Assumptions

- Single Kafka cluster (no cross-region replication)
- UTC timestamps for all events
- Market hours not considered for rate limiting
- Schema evolution via compatible changes only

## CI/CD

### CI Pipeline (.github/workflows/ci.yml)

1. **Lint** (ruff) - Fast fail on style issues
2. **Type Check** (mypy) - Catch type errors
3. **Unit Tests** (pytest) - Core logic validation
4. **Build** (Docker) - Multi-stage images
5. **Security Scan** (Trivy) - CVE detection
6. **Integration Tests** - End-to-end validation

### Local CD Simulation

```bash
# Rolling update simulation
./scripts/local-cd.sh

# Rollback if needed
./scripts/rollback.sh
```

## License

MIT
