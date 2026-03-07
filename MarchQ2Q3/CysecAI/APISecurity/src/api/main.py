"""FastAPI scanner API — wraps all security testers behind a REST interface."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import health, scans

app = FastAPI(
    title="APISecurity Scanner API",
    description="REST API for the OWASP API Security Top 10 scanner.",
    version="1.0.0",
)

app.include_router(health.router)
app.include_router(scans.router)
