# ML Feature Store

A production-grade ML Feature Store with batch and stream compute, online/offline serving, point-in-time correct training dataset generation, and feature drift monitoring.

## Architecture

- **Registry**: Feature definitions, versioning, lineage tracking, dependency resolution
- **Compute**: Batch (SQL aggregations) and stream (Kafka + Redis state) engines
- **Storage**: Offline (Postgres/TimescaleDB) and online (Redis) stores
- **Serving**: Online (low-latency), batch (PIT joins), training dataset builder
- **Monitoring**: Freshness SLA, drift detection (PSI/chi-squared), data quality

## Quick Start

```bash
# Start infrastructure
docker compose up -d

# Seed sample data
python -m simulation.seed

# Run simulation
python -m simulation.simulator

# API docs
open http://localhost:8060/docs
```

## Development

```bash
# Install
conda activate upskill
pip install -e ".[dev]"

# Lint
make lint

# Test
make test

# Type check
make typecheck
```

## Services

| Service | Port |
|---------|------|
| API | 8060 |
| Postgres | 5432 |
| Redis | 6380 |
| Redpanda | 9093 |
| Prometheus | 9090 |
| Grafana | 3060 |
