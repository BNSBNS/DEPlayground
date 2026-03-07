# Data Contracts & Governance

Schema enforcement, quality checks, SLA tracking, and ownership governance for data pipelines.

## Features

- **Contract Registry** — YAML-defined contracts with versioning and semver diffing
- **Schema Enforcement** — validate actual database schemas against contract specs
- **Quality Checks** — freshness, volume, completeness, uniqueness rules
- **SLA Tracking** — update frequency, latency, availability monitoring
- **Governance** — team ownership mapping, consumer tracking, audit log
- **Notifications** — Slack alerts on violations and SLA breaches

## Quick Start

```bash
# Dev setup (conda)
conda activate upskill
pip install -e ".[dev]"

# Lint & format
make lint

# Run tests
make test

# Start services
docker-compose up -d
make run
```

## Architecture

```
contracts/*.yml    →  Parser  →  Registry (Postgres)
                                     ↓
Enforcement Loop   →  Schema / Quality / SLA checks
                                     ↓
                        Violations  →  Notifications (Slack)
                        Audit Log   →  Governance queries
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/health | Health check |
| GET | /api/v1/contracts | List contracts |
| POST | /api/v1/contracts | Create contract |
| GET | /api/v1/contracts/{id} | Get contract |
| POST | /api/v1/contracts/{id}/versions | Publish version |
| GET | /api/v1/contracts/{id}/diff/{v1}/{v2} | Diff versions |
| POST | /api/v1/enforce/{dataset} | Run enforcement |
| GET | /api/v1/violations | List violations |
| GET | /api/v1/sla/{contract_id} | SLA records |
| GET | /api/v1/ownership | Ownership queries |

## Configuration

All via environment variables — see `.env.example`.
