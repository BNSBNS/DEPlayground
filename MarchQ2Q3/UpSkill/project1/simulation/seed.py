"""Seed script — creates simulated tables and populates historical data for dev/study.

What this creates:
  - 4 simulated domain tables: sim_events, sim_orders, sim_products, sim_sales
  - Lineage graph edges (stored in DB): sim_events → sim_orders → sim_sales
  - 30 days of historical VOLUME metrics per table (needed by z-score detector)
  - 5 resolved historical alerts (study examples of past incidents)

Run:
    python -m simulation.seed          # from project root
    make seed                          # via Makefile shortcut

Prerequisites:
    make docker-up   (Postgres must be running)
    pip install -e ".[dev]"
"""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg

from src.config import get_settings
from src.db.pool import create_tables

# ── Simulated table row counts ────────────────────────────────────────────────
BASELINE_COUNTS: dict[str, int] = {
    "sim_events": 5_000,
    "sim_orders": 2_000,
    "sim_products": 200,
    "sim_sales": 1_000,
}

# ── Lineage: (upstream, downstream, relationship) ────────────────────────────
LINEAGE_EDGES = [
    ("default.public.sim_events", "default.public.sim_orders", "DERIVED_FROM"),
    ("default.public.sim_products", "default.public.sim_orders", "DEPENDS_ON"),
    ("default.public.sim_orders", "default.public.sim_sales", "FEEDS_INTO"),
]

# DDL for the simulated domain tables (NOT the observability tables)
_SIMULATED_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS sim_events (
    id         SERIAL PRIMARY KEY,
    event_type TEXT        NOT NULL,
    payload    JSONB       NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sim_orders (
    id          SERIAL PRIMARY KEY,
    customer_id INT          NOT NULL,
    amount      NUMERIC(12,2) NOT NULL,
    status      TEXT          NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sim_products (
    id         SERIAL PRIMARY KEY,
    name       TEXT          NOT NULL,
    category   TEXT          NOT NULL,
    price      NUMERIC(10,2) NOT NULL,
    stock      INT           NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sim_sales (
    id         SERIAL PRIMARY KEY,
    order_id   INT           NOT NULL,
    product_id INT           NOT NULL,
    quantity   INT           NOT NULL,
    revenue    NUMERIC(12,2) NOT NULL,
    sale_date  DATE          NOT NULL DEFAULT CURRENT_DATE,
    updated_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
"""


async def _seed_sim_events(conn: asyncpg.Connection) -> None:
    count: int = await conn.fetchval("SELECT COUNT(*) FROM sim_events")
    if count:
        print(f"  sim_events: {count} rows already present, skipping")
        return
    event_types = ["click", "view", "purchase", "search", "logout", "signup"]
    rows = [
        (
            random.choice(event_types),
            json.dumps({"session": str(uuid.uuid4()), "user_id": random.randint(1, 1_000)}),
            datetime.now(tz=timezone.utc) - timedelta(minutes=random.randint(0, 10_080)),
        )
        for _ in range(BASELINE_COUNTS["sim_events"])
    ]
    await conn.executemany(
        "INSERT INTO sim_events (event_type, payload, updated_at) VALUES ($1, $2::jsonb, $3)",
        rows,
    )
    print(f"  sim_events: inserted {len(rows)} rows")


async def _seed_sim_products(conn: asyncpg.Connection) -> None:
    count: int = await conn.fetchval("SELECT COUNT(*) FROM sim_products")
    if count:
        print(f"  sim_products: {count} rows already present, skipping")
        return
    categories = ["Electronics", "Clothing", "Food", "Books", "Toys", "Sports"]
    rows = [
        (
            f"Product {i:04d}",
            random.choice(categories),
            round(random.uniform(10.0, 500.0), 2),  # prices: $10–$500 (normal range)
            random.randint(0, 1_000),
        )
        for i in range(1, BASELINE_COUNTS["sim_products"] + 1)
    ]
    await conn.executemany(
        "INSERT INTO sim_products (name, category, price, stock) VALUES ($1, $2, $3, $4)",
        rows,
    )
    print(f"  sim_products: inserted {len(rows)} rows (prices $10–$500)")


async def _seed_sim_orders(conn: asyncpg.Connection) -> None:
    count: int = await conn.fetchval("SELECT COUNT(*) FROM sim_orders")
    if count:
        print(f"  sim_orders: {count} rows already present, skipping")
        return
    statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
    rows = [
        (
            random.randint(1, 500),
            round(random.uniform(20.0, 2_000.0), 2),
            random.choice(statuses),
            datetime.now(tz=timezone.utc) - timedelta(minutes=random.randint(0, 43_200)),
        )
        for _ in range(BASELINE_COUNTS["sim_orders"])
    ]
    await conn.executemany(
        "INSERT INTO sim_orders (customer_id, amount, status, updated_at) VALUES ($1, $2, $3, $4)",
        rows,
    )
    print(f"  sim_orders: inserted {len(rows)} rows")


async def _seed_sim_sales(conn: asyncpg.Connection) -> None:
    count: int = await conn.fetchval("SELECT COUNT(*) FROM sim_sales")
    if count:
        print(f"  sim_sales: {count} rows already present, skipping")
        return
    rows = [
        (
            random.randint(1, BASELINE_COUNTS["sim_orders"]),
            random.randint(1, BASELINE_COUNTS["sim_products"]),
            random.randint(1, 10),
            round(random.uniform(20.0, 1_000.0), 2),
            (datetime.now(tz=timezone.utc) - timedelta(days=random.randint(0, 30))).date(),
        )
        for _ in range(BASELINE_COUNTS["sim_sales"])
    ]
    await conn.executemany(
        "INSERT INTO sim_sales (order_id, product_id, quantity, revenue, sale_date)"
        " VALUES ($1, $2, $3, $4, $5)",
        rows,
    )
    print(f"  sim_sales: inserted {len(rows)} rows")


async def _seed_lineage(conn: asyncpg.Connection) -> None:
    inserted = 0
    for upstream, downstream, relationship in LINEAGE_EDGES:
        result = await conn.execute(
            """
            INSERT INTO lineage_edges (source_id, target_id, relationship)
            VALUES ($1, $2, $3)
            ON CONFLICT (source_id, target_id, relationship) DO NOTHING
            """,
            upstream,
            downstream,
            relationship,
        )
        if result == "INSERT 0 1":
            inserted += 1
    print(f"  lineage_edges: {inserted} new edges ({len(LINEAGE_EDGES)} total defined)")


async def _seed_historical_metrics(conn: asyncpg.Connection) -> None:
    """Insert 30 days of daily volume checks for each table.

    The volume detector (z-score) requires historical data points to compare
    current count against. Without this, it returns UNKNOWN status.
    The seed provides a realistic baseline with ±15% daily variation and
    weekend seasonality (~85% of weekday volume).
    """
    existing: int = await conn.fetchval("SELECT COUNT(*) FROM data_quality_metrics")
    if existing:
        print(f"  data_quality_metrics: {existing} rows already present, skipping")
        return

    now = datetime.now(tz=timezone.utc)
    rows = []
    for table_name in BASELINE_COUNTS:
        baseline = BASELINE_COUNTS[table_name]
        for day_offset in range(30, 0, -1):
            measured_at = now - timedelta(days=day_offset)
            # Weekend seasonality: Saturday=5, Sunday=6
            seasonal = 0.85 if measured_at.weekday() >= 5 else 1.0
            daily_count = int(baseline * seasonal * random.uniform(0.88, 1.12))
            rows.append((
                uuid.uuid4(),
                table_name,
                "default",
                "public",
                "volume",
                float(daily_count),
                None,   # expected_value
                2.0,    # threshold_warning (z-score)
                3.0,    # threshold_critical (z-score)
                "healthy",
                json.dumps({"zscore": 0.0, "historical_count": day_offset - 1, "lookback_days": 14}),
                measured_at,
            ))
    await conn.executemany(
        """
        INSERT INTO data_quality_metrics
            (id, table_name, database, schema_name, metric_type, value,
             expected_value, threshold_warning, threshold_critical,
             status, metadata, measured_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)
        """,
        rows,
    )
    print(f"  data_quality_metrics: {len(rows)} historical volume records (30d × 4 tables)")


async def _seed_historical_alerts(conn: asyncpg.Connection) -> None:
    """Insert 5 resolved historical alerts — useful study examples of past incidents."""
    existing: int = await conn.fetchval("SELECT COUNT(*) FROM alerts")
    if existing:
        print(f"  alerts: {existing} rows already present, skipping")
        return

    now = datetime.now(tz=timezone.utc)
    examples = [
        (
            "sim_orders volume drop",
            "Row count fell 40% below 14-day average (z-score: -3.2)",
            "critical",
            "sim_orders",
            "volume",
            "sim_events pipeline delayed — upstream event processing backlog",
            "Review Airflow DAG 'events_to_orders'; check consumer lag",
        ),
        (
            "sim_events freshness alert",
            "Data was 95 minutes stale (threshold: 60 min warning / 120 min critical)",
            "warning",
            "sim_events",
            "freshness",
            None,
            "Check event producer health and Kafka consumer lag",
        ),
        (
            "sim_sales unexpected schema change",
            "New column added: 'discount_pct NUMERIC(5,2)'",
            "warning",
            "sim_sales",
            "schema",
            None,
            "Verify schema change was intentional; update downstream pipelines",
        ),
        (
            "sim_products price distribution shift",
            "KS test p-value: 0.002 (threshold: critical < 0.01) — significant price distribution change",
            "critical",
            "sim_products",
            "distribution",
            "Bulk import of luxury items raised mean price from $180 to $420",
            "Review recent product imports; recompute recommendation model baselines",
        ),
        (
            "sim_orders volume spike",
            "Row count 3.5x above 14-day average — possible duplicate ingestion",
            "critical",
            "sim_orders",
            "volume",
            "ETL job ran twice due to Airflow retry misconfiguration",
            "Deduplicate orders table; fix idempotency key in ETL job",
        ),
    ]
    for title, description, severity, source_table, metric_type, root_cause, remediation in examples:
        created = now - timedelta(days=random.randint(3, 25))
        resolved = created + timedelta(hours=random.randint(1, 6))
        await conn.execute(
            """
            INSERT INTO alerts
                (id, title, description, severity, state, source_table, source_metric_type,
                 root_cause, suggested_remediation, created_at, resolved_at)
            VALUES ($1,$2,$3,$4,'resolved',$5,$6,$7,$8,$9,$10)
            """,
            uuid.uuid4(),
            title,
            description,
            severity,
            source_table,
            metric_type,
            root_cause,
            remediation,
            created,
            resolved,
        )
    print(f"  alerts: {len(examples)} resolved historical alerts seeded")


async def seed(pool: asyncpg.Pool) -> None:
    # 1. Observability tables (metrics, alerts, lineage_edges, etc.)
    await create_tables(pool)
    print("Observability tables: ready")

    # 2. Simulated domain tables
    async with pool.acquire() as conn:
        await conn.execute(_SIMULATED_TABLES_DDL)
    print("Simulated domain tables: created")

    # 3. Seed domain data
    print("\nSeeding domain data:")
    async with pool.acquire() as conn:
        await _seed_sim_events(conn)
        await _seed_sim_products(conn)
        await _seed_sim_orders(conn)
        await _seed_sim_sales(conn)

    # 4. Lineage graph edges (DB-persisted — simulator loads these into memory)
    print("\nSeeding lineage:")
    async with pool.acquire() as conn:
        await _seed_lineage(conn)

    # 5. Historical metrics (30-day volume baseline for z-score detector)
    print("\nSeeding historical metrics:")
    async with pool.acquire() as conn:
        await _seed_historical_metrics(conn)

    # 6. Resolved historical alerts (examples of past incidents)
    print("\nSeeding historical alerts:")
    async with pool.acquire() as conn:
        await _seed_historical_alerts(conn)

    print("\nSeed complete! Run `make simulate` to start continuous event generation.")


async def main() -> None:
    settings = get_settings()
    pool: asyncpg.Pool = await asyncpg.create_pool(
        dsn=settings.postgres.get_dsn(),
        min_size=2,
        max_size=5,
    )
    try:
        await seed(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
