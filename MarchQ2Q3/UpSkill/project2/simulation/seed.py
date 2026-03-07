"""Seed the ingestion store with sample data for development and demos."""

from __future__ import annotations

import json
import random
from pathlib import Path
from uuid import uuid4

import structlog
import yaml

from src.ingestion.store import store

log = structlog.get_logger(__name__)

SAMPLE_DATA_DIR = Path(__file__).parent / "sample_data"

# --- Database / Schema / Table / Column hierarchy ---

DATABASES = ["warehouse", "analytics_db", "ml_platform"]

SCHEMAS: dict[str, list[str]] = {
    "warehouse": [
        "raw", "staging", "intermediate", "marts",
        "metrics", "reporting", "finance",
    ],
    "analytics_db": [
        "customer_analytics", "product_analytics",
        "marketing", "session_data",
    ],
    "ml_platform": [
        "ml_features", "model_registry",
        "experiment_tracking", "serving",
    ],
}

TABLES: dict[str, list[dict[str, str | int]]] = {
    "raw": [
        {"name": "orders", "rows": 1_200_000, "desc": "Raw transactional orders"},
        {"name": "customers", "rows": 85_000, "desc": "Raw customer records"},
        {"name": "payments", "rows": 1_500_000, "desc": "Payment transactions"},
        {"name": "products", "rows": 4_200, "desc": "Product catalog"},
        {"name": "sessions", "rows": 5_000_000, "desc": "Clickstream sessions"},
        {"name": "inventory", "rows": 42_000, "desc": "Inventory levels"},
        {"name": "suppliers", "rows": 320, "desc": "Supplier directory"},
        {"name": "warehouses", "rows": 12, "desc": "Warehouse locations"},
    ],
    "staging": [
        {"name": "stg_orders", "rows": 1_180_000, "desc": "Staged orders"},
        {"name": "stg_customers", "rows": 84_500, "desc": "Staged customers"},
        {"name": "stg_payments", "rows": 1_480_000, "desc": "Staged payments"},
        {"name": "stg_products", "rows": 4_200, "desc": "Staged products"},
        {"name": "stg_sessions", "rows": 4_900_000, "desc": "Staged sessions"},
        {"name": "stg_inventory", "rows": 42_000, "desc": "Staged inventory"},
    ],
    "intermediate": [
        {"name": "int_order_payments", "rows": 1_100_000, "desc": "Joined order-payment"},
        {"name": "int_customer_sessions", "rows": 84_000, "desc": "Aggregated sessions"},
    ],
    "marts": [
        {"name": "orders_mart", "rows": 1_100_000, "desc": "Order fact table"},
        {"name": "customers_mart", "rows": 84_500, "desc": "Customer dimension"},
        {"name": "products_mart", "rows": 4_200, "desc": "Product performance"},
        {"name": "supplier_performance", "rows": 320, "desc": "Supplier metrics"},
        {"name": "marketing_attribution", "rows": 250_000, "desc": "Channel attribution"},
    ],
    "metrics": [
        {"name": "revenue_daily", "rows": 365, "desc": "Daily revenue by category"},
        {"name": "customer_cohorts", "rows": 2_400, "desc": "Monthly cohort retention"},
        {"name": "inventory_alerts", "rows": 180, "desc": "Low stock alerts"},
        {"name": "session_funnel", "rows": 365, "desc": "Conversion funnel"},
    ],
    "reporting": [
        {"name": "exec_summary", "rows": 365, "desc": "Executive daily summary"},
    ],
    "finance": [
        {"name": "payment_reconciliation", "rows": 365, "desc": "Daily reconciliation"},
    ],
    "customer_analytics": [
        {"name": "customer_segments", "rows": 84_500, "desc": "RFM segments"},
        {"name": "customer_events", "rows": 2_000_000, "desc": "Event stream"},
        {"name": "churn_scores", "rows": 84_500, "desc": "Churn probability scores"},
    ],
    "product_analytics": [
        {"name": "product_views", "rows": 8_000_000, "desc": "Product page views"},
        {"name": "product_recommendations", "rows": 42_000, "desc": "Collaborative filtering"},
    ],
    "marketing": [
        {"name": "campaigns", "rows": 450, "desc": "Campaign definitions"},
        {"name": "campaign_performance", "rows": 4_500, "desc": "Campaign metrics"},
        {"name": "ab_test_results", "rows": 120, "desc": "A/B test outcomes"},
    ],
    "session_data": [
        {"name": "session_events", "rows": 15_000_000, "desc": "Raw session events"},
        {"name": "session_summaries", "rows": 5_000_000, "desc": "Summarized sessions"},
    ],
    "ml_features": [
        {"name": "churn_prediction_features", "rows": 84_500, "desc": "Churn model features"},
        {"name": "ltv_features", "rows": 84_500, "desc": "Lifetime value features"},
        {"name": "recommendation_features", "rows": 4_200, "desc": "Product rec features"},
    ],
    "model_registry": [
        {"name": "models", "rows": 25, "desc": "Registered ML models"},
        {"name": "model_versions", "rows": 150, "desc": "Model version history"},
    ],
    "experiment_tracking": [
        {"name": "experiments", "rows": 80, "desc": "ML experiments"},
        {"name": "runs", "rows": 500, "desc": "Experiment runs"},
        {"name": "metrics_log", "rows": 5_000, "desc": "Run metrics"},
    ],
    "serving": [
        {"name": "predictions", "rows": 200_000, "desc": "Model predictions"},
        {"name": "feature_cache", "rows": 84_500, "desc": "Online feature cache"},
    ],
}

COLUMN_TYPES = ["uuid", "varchar", "integer", "numeric(18,2)", "date", "timestamptz", "boolean"]


def _generate_columns(table_name: str) -> list[dict[str, str]]:
    """Generate plausible columns for a table based on its name."""
    base = [
        {"name": "id", "type": "uuid", "desc": "Primary key"},
        {"name": "created_at", "type": "timestamptz", "desc": "Record creation timestamp"},
    ]
    if "customer" in table_name:
        base.extend([
            {"name": "customer_id", "type": "uuid", "desc": "Customer identifier"},
            {"name": "email", "type": "varchar", "desc": "Email address"},
            {"name": "name", "type": "varchar", "desc": "Customer name"},
        ])
    if "order" in table_name:
        base.extend([
            {"name": "order_id", "type": "uuid", "desc": "Order identifier"},
            {"name": "total_amount", "type": "numeric(18,2)", "desc": "Order total"},
            {"name": "status", "type": "varchar", "desc": "Order status"},
        ])
    if "product" in table_name:
        base.extend([
            {"name": "product_id", "type": "uuid", "desc": "Product identifier"},
            {"name": "category", "type": "varchar", "desc": "Product category"},
            {"name": "price", "type": "numeric(18,2)", "desc": "Unit price"},
        ])
    if "payment" in table_name:
        base.extend([
            {"name": "payment_id", "type": "uuid", "desc": "Payment identifier"},
            {"name": "amount", "type": "numeric(18,2)", "desc": "Payment amount"},
            {"name": "method", "type": "varchar", "desc": "Payment method"},
        ])
    if "session" in table_name:
        base.extend([
            {"name": "session_id", "type": "uuid", "desc": "Session identifier"},
            {"name": "page_views", "type": "integer", "desc": "Page view count"},
        ])
    # Ensure at least 5 columns
    while len(base) < 5:
        col_type = random.choice(COLUMN_TYPES)
        base.append({
            "name": f"col_{len(base)}",
            "type": col_type,
            "desc": f"Auto-generated column ({col_type})",
        })
    return base


METRICS = [
    ("revenue_daily", "SUM(order_total)", "orders_mart"),
    ("customer_lifetime_value", "SUM(order_total) per customer", "customers_mart"),
    ("monthly_active_users", "COUNT(DISTINCT customer_id)", "session_summaries"),
    ("avg_order_value", "AVG(order_total)", "orders_mart"),
    ("conversion_rate", "purchases / sessions", "session_funnel"),
    ("churn_rate", "churned / total customers", "customer_cohorts"),
    ("days_until_stockout", "current_stock / daily_velocity", "inventory_alerts"),
    ("reorder_point", "lead_time * daily_velocity", "inventory_alerts"),
    ("collection_rate", "collected / expected", "payment_reconciliation"),
    ("cpa", "spend / attributed_orders", "marketing_attribution"),
    ("roas", "attributed_revenue / spend", "marketing_attribution"),
    ("fulfillment_rate", "fulfilled / total", "supplier_performance"),
    ("defect_rate", "defects / total", "supplier_performance"),
    ("prediction_accuracy", "correct / total predictions", "predictions"),
    ("feature_drift", "PSI score", "feature_cache"),
]


def seed() -> dict[str, int]:
    """Populate the ingestion store with sample graph data."""
    store.clear()
    node_count = 0
    edge_count = 0

    # --- Databases ---
    db_ids: dict[str, str] = {}
    for db_name in DATABASES:
        nid = str(uuid4())
        store.add_node(nid, "database", db_name, description=f"{db_name} database")
        db_ids[db_name] = nid
        node_count += 1

    # --- Schemas ---
    schema_ids: dict[str, str] = {}
    for db_name, schema_list in SCHEMAS.items():
        for schema_name in schema_list:
            nid = str(uuid4())
            store.add_node(nid, "schema", schema_name, database=db_name)
            schema_ids[schema_name] = nid
            store.add_edge(nid, db_ids[db_name], "belongs_to")
            node_count += 1
            edge_count += 1

    # --- Tables + Columns ---
    table_ids: dict[str, str] = {}
    total_columns = 0
    for schema_name, table_list in TABLES.items():
        db_name = next(
            db for db, schemas in SCHEMAS.items() if schema_name in schemas
        )
        for tbl in table_list:
            tbl_name = str(tbl["name"])
            tbl_id = str(uuid4())
            store.add_node(
                tbl_id, "table", tbl_name,
                schema_name=schema_name,
                database=db_name,
                row_count=tbl["rows"],
                description=str(tbl["desc"]),
            )
            table_ids[tbl_name] = tbl_id
            store.add_edge(tbl_id, schema_ids[schema_name], "belongs_to")
            node_count += 1
            edge_count += 1

            # Columns
            for col in _generate_columns(tbl_name):
                col_id = str(uuid4())
                store.add_node(
                    col_id, "column", col["name"],
                    table=tbl_name,
                    data_type=col["type"],
                    description=col["desc"],
                )
                store.add_edge(col_id, tbl_id, "belongs_to")
                node_count += 1
                edge_count += 1
                total_columns += 1

    # --- dbt models ---
    manifest_path = SAMPLE_DATA_DIR / "dbt_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    dbt_ids: dict[str, str] = {}
    for node_key, node_data in manifest["nodes"].items():
        model_name = node_data["name"]
        nid = str(uuid4())
        deps = node_data.get("depends_on", {}).get("nodes", [])
        store.add_node(
            nid, "dbt_model", model_name,
            materialization=node_data["materialization"],
            schema_name=node_data["schema"],
            description=node_data.get("description", ""),
            depends_on=deps,
        )
        dbt_ids[node_key] = nid
        node_count += 1

        # Link to table if it exists
        if model_name in table_ids:
            store.add_edge(nid, table_ids[model_name], "materializes")
            edge_count += 1

    # dbt dependency edges
    for node_key, node_data in manifest["nodes"].items():
        for dep_key in node_data.get("depends_on", {}).get("nodes", []):
            source_id = dbt_ids.get(dep_key)
            target_id = dbt_ids.get(node_key)
            if source_id and target_id:
                store.add_edge(target_id, source_id, "depends_on")
                edge_count += 1
            elif dep_key.startswith("source."):
                # Link from dbt model to source table
                source_name = dep_key.split(".")[-1]
                if source_name in table_ids:
                    store.add_edge(
                        dbt_ids[node_key], table_ids[source_name], "sources"
                    )
                    edge_count += 1

    # --- Dashboards ---
    dashboards_path = SAMPLE_DATA_DIR / "dashboards.json"
    dashboards = json.loads(dashboards_path.read_text())
    dash_ids: dict[str, str] = {}
    for dash in dashboards:
        nid = str(uuid4())
        store.add_node(
            nid, "dashboard", dash["name"],
            tool=dash["tool"],
            url=dash["url"],
            owner=dash["owner"],
        )
        dash_ids[dash["name"]] = nid
        node_count += 1

        for tbl_name in dash.get("tables", []):
            if tbl_name in table_ids:
                store.add_edge(nid, table_ids[tbl_name], "uses")
                edge_count += 1

    # --- Metrics ---
    metric_ids: dict[str, str] = {}
    for metric_name, expression, source_table in METRICS:
        nid = str(uuid4())
        store.add_node(
            nid, "metric", metric_name,
            expression=expression,
            table=source_table,
        )
        metric_ids[metric_name] = nid
        node_count += 1

        if source_table in table_ids:
            store.add_edge(nid, table_ids[source_table], "derived_from")
            edge_count += 1

    # Link dashboards to metrics
    for dash in dashboards:
        for metric_name in dash.get("metrics", []):
            if metric_name in metric_ids and dash["name"] in dash_ids:
                store.add_edge(dash_ids[dash["name"]], metric_ids[metric_name], "displays")
                edge_count += 1

    # --- Owners ---
    owners_path = SAMPLE_DATA_DIR / "owners.yml"
    owners_data = yaml.safe_load(owners_path.read_text())
    owner_ids: dict[str, str] = {}
    for owner in owners_data["owners"]:
        nid = str(uuid4())
        store.add_node(
            nid, "owner", owner["name"],
            team=owner["team"],
            email=owner["email"],
        )
        owner_ids[owner["name"]] = nid
        node_count += 1

        for asset_ref in owner.get("owns", []):
            asset_type, asset_name = asset_ref.split(":", 1)
            lookup: dict[str, dict[str, str]] = {
                "schema": schema_ids,
                "database": db_ids,
                "dashboard": dash_ids,
                "dbt_model": {
                    v["name"]: k
                    for k, v in manifest["nodes"].items()
                    if v["name"] in [asset_name]
                },
            }
            target_map = lookup.get(asset_type, {})
            # For dbt_model, resolve through dbt_ids
            if asset_type == "dbt_model":
                for dbt_key, dbt_nid in dbt_ids.items():
                    if manifest["nodes"].get(dbt_key, {}).get("name") == asset_name:
                        store.add_edge(dbt_nid, nid, "owned_by")
                        edge_count += 1
                        break
            elif asset_name in target_map:
                store.add_edge(target_map[asset_name], nid, "owned_by")
                edge_count += 1

    # --- Document chunks ---
    docs_dir = SAMPLE_DATA_DIR / "docs"
    chunk_count = 0
    for doc_path in sorted(docs_dir.glob("*.md")):
        doc_id = str(uuid4())
        content = doc_path.read_text(encoding="utf-8")
        store.add_node(
            doc_id, "document", doc_path.stem,
            source_path=str(doc_path),
            content=content[:200],
        )
        node_count += 1

        # Split into chunks (~512 chars)
        chunk_size = 512
        overlap = 50
        pos = 0
        idx = 0
        while pos < len(content):
            chunk_text = content[pos : pos + chunk_size]
            chunk_id = str(uuid4())
            store.add_node(
                chunk_id, "document_chunk", f"{doc_path.stem}_chunk_{idx}",
                document_id=doc_id,
                content=chunk_text,
                chunk_index=idx,
            )
            store.add_edge(chunk_id, doc_id, "part_of")
            node_count += 1
            edge_count += 1
            chunk_count += 1
            idx += 1
            pos += chunk_size - overlap

        # Link documents to tables/models they describe
        content_lower = content.lower()
        for tbl_name, tbl_id in table_ids.items():
            if tbl_name.lower() in content_lower:
                store.add_edge(doc_id, tbl_id, "describes")
                edge_count += 1

    stats = {
        "databases": len(DATABASES),
        "schemas": sum(len(v) for v in SCHEMAS.values()),
        "tables": sum(len(v) for v in TABLES.values()),
        "columns": total_columns,
        "dbt_models": len(manifest["nodes"]),
        "dashboards": len(dashboards),
        "metrics": len(METRICS),
        "owners": len(owners_data["owners"]),
        "document_chunks": chunk_count,
        "total_nodes": node_count,
        "total_edges": edge_count,
    }
    log.info("seed_complete", **stats)
    return stats


if __name__ == "__main__":
    result = seed()
    for key, val in result.items():
        print(f"  {key}: {val}")
