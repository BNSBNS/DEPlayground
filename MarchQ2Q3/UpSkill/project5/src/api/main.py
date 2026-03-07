from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routers import contracts, enforcement, health, ownership, sla, violations
from src.db.pool import close_pool, init_pool
from src.enforcement.webhook import router as webhook_router
from src.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log.info("starting_data_contracts_api")
    await init_pool()
    yield
    await close_pool()
    log.info("data_contracts_api_stopped")


app = FastAPI(
    title="Data Contracts & Governance",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount all routers under /api/v1
app.include_router(health.router, prefix="/api/v1")
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(enforcement.router, prefix="/api/v1")
app.include_router(violations.router, prefix="/api/v1")
app.include_router(sla.router, prefix="/api/v1")
app.include_router(ownership.router, prefix="/api/v1")
app.include_router(webhook_router, prefix="/api/v1")
