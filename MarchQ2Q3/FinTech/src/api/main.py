"""FastAPI application factory with lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import APIKeyMiddleware, RequestIDMiddleware
from src.api.routes import backtest, health, options, research, signals
from src.config import get_settings
from src.logging import configure_logging, get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown."""
    configure_logging()
    logger.info("app_starting")
    yield
    logger.info("app_shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="FinTech Intelligence Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health.router)
    app.include_router(research.router)
    app.include_router(signals.router)
    app.include_router(options.router)
    app.include_router(backtest.router)

    return app


app = create_app()
