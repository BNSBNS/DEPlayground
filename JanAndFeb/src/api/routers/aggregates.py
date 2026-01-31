"""REST endpoints for trade aggregates.

Reads from PostgreSQL trade_aggregates table.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

router = APIRouter()


class AggregateResponse(BaseModel):
    """Trade aggregate response model."""

    symbol: str
    window_start: datetime
    window_end: datetime
    vwap: Decimal = Field(decimal_places=8)
    total_volume: Decimal = Field(decimal_places=8)
    trade_count: int
    max_price: Decimal = Field(decimal_places=8)
    min_price: Decimal = Field(decimal_places=8)


class VWAPResponse(BaseModel):
    """VWAP summary response."""

    symbol: str
    vwap: Decimal = Field(decimal_places=8)
    total_volume: Decimal = Field(decimal_places=8)
    trade_count: int
    period_start: datetime
    period_end: datetime


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    data: list[AggregateResponse]
    total: int
    limit: int
    offset: int


@router.get("/aggregates", response_model=PaginatedResponse)
async def get_aggregates(
    request: Request,
    symbol: Annotated[str | None, Query(description="Filter by symbol")] = None,
    hours: Annotated[int, Query(ge=1, le=168, description="Hours of data")] = 24,
    limit: Annotated[int, Query(ge=1, le=1000, description="Max results")] = 100,
    offset: Annotated[int, Query(ge=0, description="Skip results")] = 0,
) -> PaginatedResponse:
    """Get trade aggregates from PostgreSQL.

    Query Parameters:
        symbol: Filter by trading symbol (e.g., POWER_DE)
        hours: Number of hours of historical data (default 24, max 168)
        limit: Maximum results to return (default 100, max 1000)
        offset: Number of results to skip for pagination
    """
    db = request.app.state.db_writer

    # Build query
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with db._get_connection() as conn:
        with conn.cursor() as cur:
            # Count total
            count_sql = """
                SELECT COUNT(*) as total
                FROM trade_aggregates
                WHERE window_start >= %(since)s
            """
            params: dict[str, str | datetime | int] = {"since": since}

            if symbol:
                count_sql += " AND symbol = %(symbol)s"
                params["symbol"] = symbol

            cur.execute(count_sql, params)
            total = cur.fetchone()["total"]

            # Get data
            data_sql = """
                SELECT symbol, window_start, window_end, vwap, total_volume,
                       trade_count, max_price, min_price
                FROM trade_aggregates
                WHERE window_start >= %(since)s
            """

            if symbol:
                data_sql += " AND symbol = %(symbol)s"

            data_sql += """
                ORDER BY window_start DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """
            params["limit"] = limit
            params["offset"] = offset

            cur.execute(data_sql, params)
            rows = cur.fetchall()

    aggregates = [AggregateResponse(**row) for row in rows]

    return PaginatedResponse(
        data=aggregates,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/aggregates/{symbol}", response_model=list[AggregateResponse])
async def get_aggregates_by_symbol(
    request: Request,
    symbol: str,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[AggregateResponse]:
    """Get aggregates for a specific symbol."""
    db = request.app.state.db_writer
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    with db._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, window_start, window_end, vwap, total_volume,
                       trade_count, max_price, min_price
                FROM trade_aggregates
                WHERE symbol = %(symbol)s AND window_start >= %(since)s
                ORDER BY window_start DESC
                LIMIT %(limit)s
                """,
                {"symbol": symbol, "since": since, "limit": limit},
            )
            rows = cur.fetchall()

    return [AggregateResponse(**row) for row in rows]


@router.get("/vwap", response_model=list[VWAPResponse])
async def get_vwap(
    request: Request,
    symbol: Annotated[str | None, Query(description="Filter by symbol")] = None,
    hours: Annotated[int, Query(ge=1, le=24, description="Hours for VWAP")] = 1,
) -> list[VWAPResponse]:
    """Get computed VWAP per symbol over the specified period.

    Computes the volume-weighted average price from stored aggregates.
    """
    db = request.app.state.db_writer
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    now = datetime.now(timezone.utc)

    with db._get_connection() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT
                    symbol,
                    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) as vwap,
                    SUM(total_volume) as total_volume,
                    SUM(trade_count) as trade_count
                FROM trade_aggregates
                WHERE window_start >= %(since)s
            """
            params: dict[str, str | datetime] = {"since": since}

            if symbol:
                sql += " AND symbol = %(symbol)s"
                params["symbol"] = symbol

            sql += " GROUP BY symbol ORDER BY symbol"

            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        VWAPResponse(
            symbol=row["symbol"],
            vwap=row["vwap"] or Decimal("0"),
            total_volume=row["total_volume"] or Decimal("0"),
            trade_count=row["trade_count"] or 0,
            period_start=since,
            period_end=now,
        )
        for row in rows
    ]


@router.get("/symbols", response_model=list[str])
async def get_symbols(request: Request) -> list[str]:
    """Get list of all trading symbols with recent data."""
    db = request.app.state.db_writer
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    with db._get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT symbol
                FROM trade_aggregates
                WHERE window_start >= %(since)s
                ORDER BY symbol
                """,
                {"since": since},
            )
            rows = cur.fetchall()

    return [row["symbol"] for row in rows]
