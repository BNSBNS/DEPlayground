"""FastAPI REST API for the SIEM detection engine.

Endpoints: GET /alerts, GET /events, GET /rules, POST /rules, GET /stats, GET /health.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Query

from src.detection.sigma_loader import parse_rule_yaml
from src.pipeline.processor import EventProcessor
from src.storage.event_store import EventStore

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


class _AppState:
    """Mutable app state."""

    def __init__(self) -> None:
        self.store = EventStore()
        self.processor = EventProcessor(rules_dir=RULES_DIR)


state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # noqa: ARG001
    """Startup/shutdown."""
    yield
    state.store.close()


app = FastAPI(
    title="SIEM Detection Engine API",
    version="1.0.0",
    description="Security event query and alert management",
    lifespan=lifespan,
)


@app.get("/api/v1/alerts")
async def get_alerts(
    severity: str | None = Query(None),
    rule_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Get alerts with optional filters."""
    alerts = state.store.query_alerts(
        severity=severity, rule_id=rule_id, limit=limit, offset=offset
    )
    return {"alerts": alerts, "count": len(alerts)}


@app.get("/api/v1/events")
async def get_events(
    src_ip: str | None = Query(None),
    user: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Search events by IP, user, or event type."""
    events = state.store.query_events(
        src_ip=src_ip, user=user, event_type=event_type, limit=limit, offset=offset
    )
    return {"events": events, "count": len(events)}


@app.get("/api/v1/rules")
async def get_rules() -> dict[str, Any]:
    """List loaded Sigma detection rules."""
    rules = state.processor.rule_engine.rules
    return {
        "rules": [
            {
                "id": r.id,
                "title": r.title,
                "level": r.level,
                "tags": r.tags,
                "mitre_technique_ids": r.mitre_technique_ids,
            }
            for r in rules
        ],
        "count": len(rules),
    }


@app.post("/api/v1/rules")
async def add_rule(yaml_content: str = Body(embed=True)) -> dict[str, str]:
    """Add a new Sigma detection rule from YAML."""
    rule = parse_rule_yaml(yaml_content)
    state.processor.rule_engine.add_rule(rule)
    return {"status": "added", "rule_id": rule.id}


@app.get("/api/v1/stats")
async def get_stats() -> dict[str, Any]:
    """Get pipeline and storage statistics."""
    storage_stats = state.store.get_stats()
    pipeline_stats = state.processor.stats
    correlation_rules = state.processor.correlation_engine.rules
    return {
        "storage": storage_stats,
        "pipeline": pipeline_stats,
        "sigma_rules_loaded": len(state.processor.rule_engine.rules),
        "correlation_rules_loaded": len(correlation_rules),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


def set_state(store: EventStore | None = None, processor: EventProcessor | None = None) -> None:
    """Inject dependencies (for testing)."""
    if store:
        state.store = store
    if processor:
        state.processor = processor
