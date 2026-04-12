"""FastAPI application for the energy trading platform.

Provides REST and WebSocket endpoints for querying trade aggregates
and streaming real-time trade events.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import aggregates, health, websocket
from src.api.services.kafka_streamer import KafkaStreamer
from src.common.config import get_settings
from src.common.logging_config import get_logger
from src.consumer.db_writer import DatabaseWriter
from src.ml.api.routes import router as ml_router
from src.ml.store.repository import (
    PostgresForecastRepository,
    PostgresModelRegistryRepository,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle - startup and shutdown."""
    settings = get_settings()

    # Initialize database writer
    logger.info("Initializing database connection")
    app.state.db_writer = DatabaseWriter(settings.postgres)

    # Wire the ML read layer.
    #
    # The API container is lean — it does NOT install torch/lightgbm/statsmodels.
    # It only reads the ``forecasts``, ``anomaly_scores``, and ``model_registry``
    # tables that the separate ``ml-scheduler`` / ``ml-trainer`` containers
    # populate. Fresh inference goes through those workers, not through the
    # API process.
    logger.info("Wiring ML read-only repositories")
    app.state.ml_forecast_repo = PostgresForecastRepository(app.state.db_writer)
    app.state.ml_registry_repo = PostgresModelRegistryRepository(app.state.db_writer)
    app.state.ml_inference = None  # fresh-inference is delegated to ml-scheduler

    # Initialize Kafka streamer for WebSocket
    logger.info("Initializing Kafka streamer")
    app.state.kafka_streamer = KafkaStreamer(settings.kafka)

    # Start the Kafka consumer in background
    app.state.streamer_task = asyncio.create_task(
        app.state.kafka_streamer.start()
    )

    logger.info("API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down API")

    # Stop Kafka streamer
    await app.state.kafka_streamer.stop()
    app.state.streamer_task.cancel()
    try:
        await app.state.streamer_task
    except asyncio.CancelledError:
        pass

    # Close database connection
    app.state.db_writer.close()

    logger.info("API shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Energy Trading Platform API",
        description="Real-time streaming API for energy trade aggregates",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware - configured via API_CORS_ORIGINS environment variable
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(aggregates.router, prefix="/api/v1", tags=["aggregates"])
    app.include_router(ml_router, prefix="/api/v1", tags=["ml"])
    app.include_router(websocket.router, tags=["websocket"])

    return app


app = create_app()


def main() -> None:
    """Run the API server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
