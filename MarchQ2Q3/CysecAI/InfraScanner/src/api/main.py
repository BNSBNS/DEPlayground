"""FastAPI application for InfraScanner."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import health, scan

app = FastAPI(
    title="InfraScanner API",
    version="0.1.0",
    description="Scan dependencies and Dockerfiles for known vulnerabilities.",
)

app.include_router(health.router)
app.include_router(scan.router)
