# Autonomous Data Engineer Agent

Self-healing data pipeline agent that detects failures, diagnoses root causes,
generates fixes, and opens PRs — all autonomously.

## Quick Start

```bash
pip install -e ".[dev]"
docker-compose up -d
uvicorn src.api.main:app --port 8030
```

## Architecture

LangGraph state machine: parse event -> gather context -> diagnose -> generate fixes
-> validate -> safety check -> create PR -> notify.

See `docs/architecture.md` for details.
