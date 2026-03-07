"""FastAPI application for the Data Observability platform."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.errors import ErrorResponse
from src.api.routers import alerts, health, lineage, metrics, rca, webhooks
from src.config import get_settings
from src.db.pool import close_pool, create_tables, init_pool
from src.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json_format)

    pool = await init_pool(settings.postgres)
    await create_tables(pool)
    logger.info("API startup complete", port=settings.api.port)

    yield

    await close_pool()
    logger.info("API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Data Observability Platform",
        description="AI-powered data quality monitoring, lineage tracking, and root cause analysis",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                detail=str(exc), error_code="VALIDATION_ERROR"
            ).model_dump(mode="json"),
        )

    app.include_router(health.router, tags=["health"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
    app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
    app.include_router(lineage.router, prefix="/api/v1", tags=["lineage"])
    app.include_router(rca.router, prefix="/api/v1", tags=["rca"])
    app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])

    return app


app = create_app()


def main() -> None:
    """Run the API server."""
    import uvicorn  # noqa: PLC0415

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=settings.api.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
