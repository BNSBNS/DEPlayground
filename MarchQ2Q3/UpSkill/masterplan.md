# Portfolio Projects — Master Plan

## Overview
Six self-contained projects forming a cohesive data + ML platform ecosystem. Each project is production-quality, containerized, and runnable via `docker compose up`. Projects can reference each other but must work independently.

**Target roles:** Data Engineering, ML Engineering, AI Engineering, Data/ML Platform Engineering. These projects collectively cover the full data + ML lifecycle: pipeline quality, knowledge retrieval, autonomous remediation, streaming infrastructure, data governance, and feature engineering + serving.

## Project Ecosystem

```
[5. Data Contracts] ──── defines schemas/SLAs for ────▶ [4. Streaming Analytics]
        │                                                        │
        │ enforces quality gates on                              │ feeds real-time events to
        ▼                                                        ▼
[1. Observability] ◀──── monitors/alerts on ──── [2. Knowledge Graph (GraphRAG)]
        │                                                        │
        │ failure events trigger                                 │ knows data assets for
        ▼                                                        ▼
[3. Autonomous Agent]                            [6. Feature Store]
        │                                                ▲    │
        │ generates fixes for pipelines                  │    │ serves features for ML
        ▼                                                │    ▼
   (data pipelines) ──── raw data flows into ────────────┘  (ML models)

  4 feeds real-time events into 6 for streaming features
  1 monitors 6 for feature freshness and drift
```

## Build Order
1. `data-observability/` — Foundation: quality checks, lineage, alerts
2. `knowledge-platform/` — Knowledge graph + NL query interface
3. `data-agent/` — Autonomous failure detection and remediation
4. `streaming-analytics/` — Real-time Kafka pipelines + serving layer
5. `data-contracts/` — Schema registry, quality gates, SLA enforcement
6. `feature-store/` — ML Feature Store: compute, version, serve, and monitor features

## Global Standards (Apply to ALL projects)

### Python & Runtime
- Python 3.13+
- Type hints everywhere, Pydantic v2 for all models
- Async where I/O is involved (database, HTTP, message queues)
- `pyproject.toml` with dependency groups (dev, test, lint)

### LLM Provider Pattern (Used in Projects 2 and 3)
Every project that uses an LLM MUST implement a provider-agnostic interface:

```
src/llm/
├── base.py          # Abstract LLMProvider: complete(messages, system, max_tokens, temperature) → LLMResponse
├── ollama.py        # Local Ollama provider (default for development)
├── anthropic.py     # Anthropic Claude provider
├── openai.py        # OpenAI provider
└── factory.py       # Factory: reads LLM_PROVIDER env var, returns the right provider
```

Design rules:
- `LLM_PROVIDER` env var selects provider: "ollama" (default), "anthropic", "openai"
- `LLM_MODEL` env var selects model: e.g., "llama3.2", "claude-sonnet-4-20250514", "gpt-4o"
- `LLM_BASE_URL` env var for custom endpoints (Ollama defaults to http://localhost:11434)
- All providers return the same `LLMResponse` model: content, usage, model, provider
- Use raw HTTP calls via `httpx` — no LangChain dependency just for LLM calls
- LangGraph is used ONLY where a proper state machine agent is needed (Project 3)
- Each provider handles its own auth: ANTHROPIC_API_KEY, OPENAI_API_KEY, or none for Ollama

### Kafka Consumer Pattern (Used in Projects 4 and 6)
Use `aiokafka` for async Kafka consumers — NOT Faust (unmaintained since 2020).
- `AIOKafkaConsumer` for consuming, `AIOKafkaProducer` for producing
- JSON serialization/deserialization via Pydantic models
- Consumer groups for parallel processing
- Manual commit for at-least-once delivery guarantees

### Simulation & Mock Data (Built into every project)
Every project MUST include:

```
simulation/
├── seed.py          # Seed script: populates DB/graph with realistic sample data
├── simulator.py     # Continuous simulator: generates ongoing events/changes for demo
├── fixtures/        # Static test fixtures (JSON/YAML) for unit tests
└── README.md        # How to run simulation mode
```

Design rules:
- `make seed` runs seed.py — one-time data population for development
- `make simulate` runs simulator.py — continuous event generation for demo/learning
- Simulation mode togglable via `SIMULATION_MODE=true` env var
- Simulators are realistic: random but weighted toward common patterns, occasional anomalies
- All fixtures in `tests/fixtures/` are static snapshots used by unit tests (no external deps)

### Project Skeleton
```
project-name/
├── docker-compose.yml
├── pyproject.toml
├── .env.example              # Every env var documented with comments
├── Makefile                  # setup, test, lint, run, seed, simulate
├── README.md                 # Setup, architecture, usage, simulation guide
├── src/
│   ├── __init__.py
│   ├── config.py             # Pydantic Settings with env var loading
│   ├── llm/                  # (if project uses LLM)
│   ├── models/               # Pydantic data models
│   ├── ... (domain modules)
│   ├── api/                  # FastAPI app
│   └── db/                   # Connection pool, Alembic migrations
├── simulation/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── grafana/dashboards/       # (if project has monitoring)
├── prometheus/               # (if project has monitoring)
└── k8s/
```

### Code Quality
- Structured logging (JSON format) via `structlog`
- Every module has a docstring
- Files under 200 lines where possible
- `ruff` for linting/formatting

### Testing
- pytest with pytest-asyncio
- Unit tests: mocks/fixtures, no external dependencies
- Integration tests: testcontainers or docker-compose services
- Every core module has at least one test file

### API Standards
- FastAPI with versioned routes (`/api/v1/...`)
- Pydantic v2 request/response models
- Health check at `/health`
- CORS middleware
- Proper HTTP status codes and error responses

### Dependencies
- Pin major versions in pyproject.toml
- `httpx` for async HTTP (over `requests`)
- `asyncpg` for PostgreSQL
- `redis.asyncio` for Redis
- `aiokafka` for Kafka (over Faust, which is unmaintained)