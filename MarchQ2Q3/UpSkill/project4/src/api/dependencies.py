from __future__ import annotations

import asyncpg

from src.db.pool import get_pool


async def get_db_pool() -> asyncpg.Pool:
    """FastAPI dependency to get the asyncpg connection pool."""
    return await get_pool()
