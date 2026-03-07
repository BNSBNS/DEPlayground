"""FastAPI application with lifespan, CORS, exception handlers, and routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from src.api.errors import ErrorResponse
from src.api.routers import evaluation, health, ingestion, query
from src.config import get_settings
from src.logging import configure_logging, get_logger

logger = get_logger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: init pool + logging. Shutdown: close pool."""
    settings = get_settings()
    configure_logging(log_level=settings.log_level, json_format=settings.log_json_format)
    logger.info("starting_graphrag_api", port=settings.api.port)

    from src.db.pool import close_pool, init_pool

    await init_pool(
        dsn=settings.postgres.get_dsn(),
        min_size=settings.postgres.pool_min,
        max_size=settings.postgres.pool_max,
    )
    yield
    await close_pool()
    logger.info("graphrag_api_shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="GraphRAG Intelligence API",
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

    # Exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        body = ErrorResponse(detail=str(exc), error_code="VALIDATION_ERROR")
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), path=request.url.path)
        body = ErrorResponse(detail="Internal server error", error_code="INTERNAL_ERROR")
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))

    # Routers
    app.include_router(health.router)
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(ingestion.router, prefix="/api/v1")
    app.include_router(evaluation.router, prefix="/api/v1")

    # Serve frontend at root
    _frontend = Path(__file__).parent.parent.parent / "frontend" / "index.html"

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_frontend() -> str:
        return _frontend.read_text()

    return app


app = create_app()


def main() -> None:
    """Entry point — run with uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=settings.api.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
