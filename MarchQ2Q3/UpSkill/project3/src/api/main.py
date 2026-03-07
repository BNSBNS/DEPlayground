from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.api.routers import approvals, events, health
from src.config import get_settings
from src.logging import setup_logging

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: init DB on startup, close on shutdown."""
    setup_logging()
    settings = get_settings()
    await log.ainfo("starting", port=settings.api_port, simulation=settings.simulation_mode)

    if not settings.simulation_mode:
        from src.db.pool import close_pool, init_db

        await init_db()
        yield
        await close_pool()
    else:
        await log.ainfo("simulation_mode_active")
        yield

    await log.ainfo("shutdown_complete")


app = FastAPI(
    title="Autonomous Data Engineer Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.api_port)
