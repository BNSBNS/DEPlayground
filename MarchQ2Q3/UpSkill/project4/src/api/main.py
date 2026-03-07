from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.errors import global_exception_handler
from src.api.routers import anomalies, customers, health, products, sales, topics, ws
from src.config import settings
from src.db.pool import close_pool, init_db
from src.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    await init_db()
    yield
    await close_pool()


app = FastAPI(
    title="Streaming Analytics API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Mount routers under /api/v1
prefix = "/api/v1"
app.include_router(health.router, prefix=prefix)
app.include_router(sales.router, prefix=prefix)
app.include_router(products.router, prefix=prefix)
app.include_router(customers.router, prefix=prefix)
app.include_router(anomalies.router, prefix=prefix)
app.include_router(topics.router, prefix=prefix)

if settings.api.ws_enabled:
    app.include_router(ws.router, prefix=prefix)
