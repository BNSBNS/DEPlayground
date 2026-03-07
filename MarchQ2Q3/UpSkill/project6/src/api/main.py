from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import asyncpg
import structlog
from fastapi import FastAPI
from redis.asyncio import Redis

from src.api.errors import FeatureStoreError, feature_store_error_handler
from src.api.routers import compute, feature_sets, features, health, monitoring, serving
from src.compute.batch.engine import BatchComputeEngine
from src.config import get_settings
from src.db.pool import close_pool, create_pool, run_migrations
from src.logging import setup_logging
from src.monitoring.freshness import FreshnessMonitor
from src.registry.catalog import FeatureCatalog
from src.serving.online import OnlineServingService
from src.serving.training import TrainingDatasetBuilder
from src.storage.offline_store import OfflineStore
from src.storage.online_store import OnlineStore

logger = structlog.get_logger(__name__)

# Global state
_pool: asyncpg.Pool | None = None
_redis: Redis | None = None
_catalog: FeatureCatalog | None = None
_batch_engine: BatchComputeEngine | None = None
_online_service: OnlineServingService | None = None
_training_builder: TrainingDatasetBuilder | None = None
_freshness_monitor: FreshnessMonitor | None = None


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database pool not initialized"
    return _pool


def get_catalog() -> FeatureCatalog:
    assert _catalog is not None, "Catalog not initialized"
    return _catalog


def get_batch_engine() -> BatchComputeEngine:
    assert _batch_engine is not None, "Batch engine not initialized"
    return _batch_engine


def get_online_service() -> OnlineServingService:
    assert _online_service is not None, "Online service not initialized"
    return _online_service


def get_training_builder() -> TrainingDatasetBuilder:
    assert _training_builder is not None, "Training builder not initialized"
    return _training_builder


def get_freshness_monitor() -> FreshnessMonitor:
    assert _freshness_monitor is not None, "Freshness monitor not initialized"
    return _freshness_monitor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _pool, _redis, _catalog, _batch_engine
    global _online_service, _training_builder, _freshness_monitor

    setup_logging()
    settings = get_settings()

    # Initialize connections
    _pool = await create_pool(settings)
    await run_migrations(_pool)

    _redis = Redis.from_url(settings.redis.url, decode_responses=True)
    await _redis.ping()

    # Initialize services
    _catalog = FeatureCatalog(_pool)
    _batch_engine = BatchComputeEngine(_pool, _redis)

    offline_store = OfflineStore(_pool)
    online_store = OnlineStore(_redis)

    _online_service = OnlineServingService(online_store)
    _training_builder = TrainingDatasetBuilder(offline_store)
    _freshness_monitor = FreshnessMonitor(offline_store)

    logger.info("feature_store_started", port=settings.api.port)
    yield

    # Cleanup
    if _redis:
        await _redis.aclose()
    if _pool:
        await close_pool(_pool)
    logger.info("feature_store_stopped")


app = FastAPI(
    title="ML Feature Store",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_exception_handler(FeatureStoreError, feature_store_error_handler)  # type: ignore[arg-type]

# Mount routers
app.include_router(health.router)
app.include_router(features.router, prefix="/api/v1")
app.include_router(feature_sets.router, prefix="/api/v1")
app.include_router(serving.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")
app.include_router(compute.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=settings.api.port,
        reload=True,
    )
