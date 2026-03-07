# Data Engineering Playground

Portfolio of data engineering and software engineering projects demonstrating production-grade patterns, real-time streaming, and system design.

## Projects

### [JanAndFeb/](JanAndFeb/) - Energy Trading Platform

Real-time analytics platform for energy market data featuring:
- Kafka streaming (KRaft mode) with windowed VWAP aggregation
- Multi-source data ingestion (WebSocket, SSE, Polling, Batch) using hexagonal architecture
- TimescaleDB storage with idempotent writes
- FastAPI REST API with WebSocket streaming
- Resilience patterns: circuit breaker, rate limiter, retry, DLQ, backpressure
- Full Docker, Kubernetes, Terraform (AWS), and CI/CD pipeline

**Stack:** Python 3.12, Kafka, PostgreSQL/TimescaleDB, FastAPI, Pydantic v2, structlog

### [MarchQ2Q3/](MarchQ2Q3/) - Q2/Q3 Projects

Collection of upskill and cybersecurity projects:
- **UpSkill/** - Data engineering portfolio projects (observability, streaming, ML pipelines)
- **CysecAI/** - Cybersecurity AI projects (network security, infrastructure scanning, API security, data security)
- **bare-agents-mcp/** - AI agent framework with MCP integration

**Stack:** Python 3.13, async I/O, Pydantic v2, structlog, ruff

## Setup

Each project has its own README with setup instructions. See the individual project directories for details.
