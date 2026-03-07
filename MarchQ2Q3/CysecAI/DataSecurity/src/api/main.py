"""DataSecurity FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers.health import router as health_router
from src.api.routers.scan import router as scan_router

app = FastAPI(
    title="DataSecurity",
    description="Database & Data Security Toolkit — PII discovery, encryption, compliance.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(scan_router)
