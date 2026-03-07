"""FastAPI application for the Network Security Monitor."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from src.api.routers import alerts, health
from src.api.routers.alerts import get_manager

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Initialize the alert manager on startup; close on shutdown."""
    manager = get_manager()
    await manager.initialize()
    yield
    await manager.close()


app = FastAPI(
    title="NetworkSecurity Monitor API",
    version="0.1.0",
    description="Analyze network packets and cloud logs for security threats.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(alerts.router)
