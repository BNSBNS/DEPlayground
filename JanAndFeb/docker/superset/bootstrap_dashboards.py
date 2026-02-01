#!/usr/bin/env python3
"""Bootstrap Superset with pre-built datasets and dashboard.

This script creates datasets from the SQL views and builds a trading dashboard.
Run this after Superset has been initialized.

Usage:
    docker exec superset python /app/bootstrap_dashboards.py
"""

import os
import sys
import time
import json

# Superset imports
from superset import app, db
from superset.connectors.sqla.models import SqlaTable
from superset.models.core import Database
from superset.models.dashboard import Dashboard
from superset.models.slice import Slice

# Chart configuration
CHART_CONFIGS = [
    {
        "name": "VWAP by Symbol (24h)",
        "viz_type": "line",
        "datasource": "v_vwap_timeseries",
        "params": {
            "metrics": ["vwap"],
            "groupby": ["symbol"],
            "x_axis": "window_start",
            "time_range": "Last 24 hours",
            "row_limit": 10000,
            "show_legend": True,
            "rich_tooltip": True,
        },
    },
    {
        "name": "Trading Volume by Symbol",
        "viz_type": "bar",
        "datasource": "v_symbol_24h_summary",
        "params": {
            "metrics": [{"label": "Total Volume", "expressionType": "SIMPLE", "column": {"column_name": "total_volume"}, "aggregate": "SUM"}],
            "groupby": ["symbol"],
            "row_limit": 20,
            "color_scheme": "supersetColors",
        },
    },
    {
        "name": "Trade Count by Symbol",
        "viz_type": "pie",
        "datasource": "v_symbol_24h_summary",
        "params": {
            "metrics": [{"label": "Total Trades", "expressionType": "SIMPLE", "column": {"column_name": "total_trades"}, "aggregate": "SUM"}],
            "groupby": ["symbol"],
            "row_limit": 10,
            "show_labels": True,
            "color_scheme": "supersetColors",
        },
    },
    {
        "name": "Volume Heatmap",
        "viz_type": "heatmap",
        "datasource": "v_volume_heatmap",
        "params": {
            "all_columns_x": "hour_of_day",
            "all_columns_y": "symbol",
            "metric": {"label": "Volume", "expressionType": "SIMPLE", "column": {"column_name": "volume"}, "aggregate": "SUM"},
            "normalize_across": "heatmap",
            "show_values": True,
        },
    },
    {
        "name": "Trading Velocity",
        "viz_type": "area",
        "datasource": "v_trading_velocity",
        "params": {
            "metrics": ["trades_per_minute", "volume_per_minute"],
            "x_axis": "minute",
            "time_range": "Last 6 hours",
            "stacked_style": "stack",
            "show_legend": True,
        },
    },
    {
        "name": "Price Bands (Bollinger)",
        "viz_type": "line",
        "datasource": "v_price_bands",
        "params": {
            "metrics": ["vwap", "ma_20", "upper_band", "lower_band"],
            "groupby": ["symbol"],
            "x_axis": "window_start",
            "time_range": "Last 24 hours",
            "row_limit": 5000,
        },
    },
    {
        "name": "Top Movers",
        "viz_type": "table",
        "datasource": "v_top_movers",
        "params": {
            "groupby": ["symbol", "hour", "pct_change", "price_change", "hour_volume"],
            "row_limit": 20,
            "order_by_cols": ["pct_change"],
            "order_desc": True,
        },
    },
    {
        "name": "Cumulative Volume",
        "viz_type": "line",
        "datasource": "v_cumulative_volume",
        "params": {
            "metrics": ["cumulative_volume"],
            "groupby": ["symbol"],
            "x_axis": "window_start",
            "time_range": "Last 24 hours",
        },
    },
    {
        "name": "DLQ Error Monitor",
        "viz_type": "bar",
        "datasource": "v_dlq_stats",
        "params": {
            "metrics": [{"label": "Error Count", "expressionType": "SIMPLE", "column": {"column_name": "error_count"}, "aggregate": "SUM"}],
            "groupby": ["error_type"],
            "time_range": "Last 7 days",
            "color_scheme": "supersetColors",
        },
    },
]

# Views to register as datasets
DATASET_VIEWS = [
    "v_symbol_24h_summary",
    "v_vwap_timeseries",
    "v_volume_heatmap",
    "v_top_movers",
    "v_trading_velocity",
    "v_lmp_breakdown",
    "v_cumulative_volume",
    "v_price_bands",
    "v_dlq_stats",
    "v_realtime_kpis",
    "trade_aggregates",
    "dlq_messages",
]


def get_or_create_database():
    """Get or create the trades database connection."""
    with app.app_context():
        database = db.session.query(Database).filter_by(database_name="trades").first()
        if not database:
            print("Creating database connection...")
            database = Database(
                database_name="trades",
                sqlalchemy_uri="postgresql://trading:trading@timescaledb:5432/trades",
                expose_in_sqllab=True,
                allow_ctas=True,
                allow_cvas=True,
                allow_dml=True,
                allow_run_async=True,
            )
            db.session.add(database)
            db.session.commit()
            print("Database connection created.")
        else:
            print("Database connection already exists.")
        return database


def create_datasets(database):
    """Create datasets from the SQL views."""
    created = []
    with app.app_context():
        for view_name in DATASET_VIEWS:
            existing = (
                db.session.query(SqlaTable)
                .filter_by(table_name=view_name, database_id=database.id)
                .first()
            )
            if existing:
                print(f"  Dataset '{view_name}' already exists, skipping...")
                continue

            print(f"  Creating dataset: {view_name}")
            dataset = SqlaTable(
                table_name=view_name,
                database_id=database.id,
                schema="public",
            )
            db.session.add(dataset)
            db.session.commit()

            # Fetch columns
            try:
                dataset.fetch_metadata()
                db.session.commit()
            except Exception as e:
                print(f"    Warning: Could not fetch metadata for {view_name}: {e}")

            created.append(view_name)

    return created


def create_charts(database):
    """Create chart slices."""
    charts = []
    with app.app_context():
        for config in CHART_CONFIGS:
            existing = db.session.query(Slice).filter_by(slice_name=config["name"]).first()
            if existing:
                print(f"  Chart '{config['name']}' already exists, skipping...")
                charts.append(existing)
                continue

            # Find the dataset
            dataset = (
                db.session.query(SqlaTable)
                .filter_by(table_name=config["datasource"], database_id=database.id)
                .first()
            )
            if not dataset:
                print(f"  Warning: Dataset '{config['datasource']}' not found, skipping chart '{config['name']}'")
                continue

            print(f"  Creating chart: {config['name']}")
            chart = Slice(
                slice_name=config["name"],
                viz_type=config["viz_type"],
                datasource_id=dataset.id,
                datasource_type="table",
                params=json.dumps(config["params"]),
            )
            db.session.add(chart)
            db.session.commit()
            charts.append(chart)

    return charts


def create_dashboard(charts):
    """Create the main trading dashboard."""
    with app.app_context():
        existing = db.session.query(Dashboard).filter_by(slug="energy-trading").first()
        if existing:
            print("Dashboard 'Energy Trading' already exists.")
            return existing

        print("Creating dashboard: Energy Trading")

        # Build position JSON for grid layout
        position_json = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID",
                "children": [],
            },
            "HEADER_ID": {
                "id": "HEADER_ID",
                "type": "HEADER",
                "meta": {"text": "Energy Trading Platform"},
            },
        }

        # Add charts to grid
        row = 0
        for i, chart in enumerate(charts):
            if chart:
                chart_id = f"CHART-{chart.id}"
                position_json["GRID_ID"]["children"].append(chart_id)
                position_json[chart_id] = {
                    "type": "CHART",
                    "id": chart_id,
                    "children": [],
                    "meta": {
                        "width": 4,
                        "height": 50,
                        "chartId": chart.id,
                        "sliceName": chart.slice_name,
                    },
                }

        dashboard = Dashboard(
            dashboard_title="Energy Trading Platform",
            slug="energy-trading",
            position_json=json.dumps(position_json),
            published=True,
        )

        # Add charts to dashboard
        dashboard.slices = [c for c in charts if c]

        db.session.add(dashboard)
        db.session.commit()
        print(f"Dashboard created with {len(dashboard.slices)} charts.")
        return dashboard


def main():
    """Main bootstrap function."""
    print("=" * 60)
    print("Superset Dashboard Bootstrap")
    print("=" * 60)

    # Wait a moment for Superset to be fully ready
    time.sleep(2)

    print("\n1. Setting up database connection...")
    database = get_or_create_database()

    print("\n2. Creating datasets from views...")
    created_datasets = create_datasets(database)
    print(f"   Created {len(created_datasets)} new datasets.")

    print("\n3. Creating charts...")
    charts = create_charts(database)
    print(f"   Created/found {len(charts)} charts.")

    print("\n4. Creating dashboard...")
    dashboard = create_dashboard(charts)

    print("\n" + "=" * 60)
    print("Bootstrap complete!")
    print("=" * 60)
    print(f"\nAccess the dashboard at:")
    print(f"  http://localhost:8088/superset/dashboard/energy-trading/")
    print("\nAvailable datasets:")
    for ds in DATASET_VIEWS:
        print(f"  - {ds}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
