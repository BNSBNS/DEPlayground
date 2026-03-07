"""Streamlit SOC Dashboard for the SIEM Detection Engine.

Run: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import GeneratorSettings
from src.data.generator import LogGenerator
from src.ingestion.normalizer import normalize_from_log_event
from src.pipeline.processor import EventProcessor
from src.storage.event_store import EventStore

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"
DB_PATH = Path(__file__).resolve().parents[2] / "siem.db"


@st.cache_resource
def get_store() -> EventStore:
    """Persistent SQLite store."""
    return EventStore(DB_PATH)


@st.cache_resource
def get_processor() -> EventProcessor:
    """Processor with Sigma rules loaded."""
    return EventProcessor(rules_dir=RULES_DIR)


def seed_data(store: EventStore, processor: EventProcessor, count: int = 500) -> int:
    """Generate and process sample events, return alert count."""
    gen = LogGenerator(GeneratorSettings(num_events=count, seed=42))
    events = gen.generate()
    alert_count = 0
    for event in events:
        normalized = normalize_from_log_event(event.model_dump())
        store.store_event(normalized)
        alerts = processor.process_event(normalized)
        for alert in alerts:
            store.store_alert(alert)
            alert_count += 1
    return alert_count


def render_overview(store: EventStore, processor: EventProcessor) -> None:
    """Top-level metrics and charts."""
    stats = store.get_stats()
    pipeline = processor.stats

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Events", stats["event_count"])
    col2.metric("Total Alerts", stats["alert_count"])
    col3.metric("Processed", pipeline.get("processed", 0))
    col4.metric("Parse Errors", pipeline.get("parse_errors", 0))

    # Alert severity distribution
    alerts = store.query_alerts(limit=1000)
    if alerts:
        severities = [a["severity"] for a in alerts]
        severity_counts = {s: severities.count(s) for s in set(severities)}
        colors = {"critical": "#dc3545", "high": "#fd7e14", "medium": "#ffc107", "low": "#28a745"}
        fig = go.Figure(
            data=[
                go.Bar(
                    x=list(severity_counts.keys()),
                    y=list(severity_counts.values()),
                    marker_color=[colors.get(s, "#6c757d") for s in severity_counts],
                )
            ]
        )
        fig.update_layout(title="Alerts by Severity", xaxis_title="Severity", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No alerts yet. Use the sidebar to generate sample data.")


def render_alerts(store: EventStore) -> None:
    """Alert browser with filters."""
    st.subheader("Alert Browser")

    col1, col2 = st.columns(2)
    severity = col1.selectbox("Severity", ["All", "critical", "high", "medium", "low"])
    limit = col2.number_input("Max results", min_value=10, max_value=500, value=50)

    sev_filter = severity if severity != "All" else None
    alerts = store.query_alerts(severity=sev_filter, limit=limit)

    if alerts:
        st.dataframe(
            [
                {
                    "Time": a["timestamp"],
                    "Type": a["alert_type"],
                    "Rule": a.get("rule_title") or a.get("rule_id", "—"),
                    "Severity": a["severity"],
                    "Source IP": a.get("src_ip", "—"),
                    "User": a.get("user", "—"),
                }
                for a in alerts
            ],
            use_container_width=True,
        )
    else:
        st.info("No alerts match the selected filters.")


def render_events(store: EventStore) -> None:
    """Event search."""
    st.subheader("Event Search")

    col1, col2, col3 = st.columns(3)
    src_ip = col1.text_input("Source IP")
    user = col2.text_input("User")
    event_type = col3.text_input("Event Type")

    events = store.query_events(
        src_ip=src_ip or None,
        user=user or None,
        event_type=event_type or None,
        limit=100,
    )

    if events:
        st.dataframe(
            [
                {
                    "Time": e["timestamp"],
                    "Source": e["source"],
                    "Type": e["event_type"],
                    "Severity": e["severity"],
                    "Src IP": e.get("src_ip", "—"),
                    "User": e.get("user", "—"),
                    "Action": e.get("action", "—"),
                }
                for e in events
            ],
            use_container_width=True,
        )
    else:
        st.info("No events match the search criteria.")


def render_rules(processor: EventProcessor) -> None:
    """Detection rules overview."""
    st.subheader("Sigma Detection Rules")
    rules = processor.rule_engine.rules
    if rules:
        st.dataframe(
            [
                {
                    "ID": r.id,
                    "Title": r.title,
                    "Level": r.level,
                    "MITRE": ", ".join(r.mitre_technique_ids),
                }
                for r in rules
            ],
            use_container_width=True,
        )
    else:
        st.info("No Sigma rules loaded.")

    st.subheader("Correlation Rules")
    corr_rules = processor.correlation_engine.rules
    if corr_rules:
        st.dataframe(
            [
                {
                    "ID": r.id,
                    "Title": r.title,
                    "Type": r.rule_type,
                    "Severity": r.severity,
                    "Window (s)": r.window_seconds,
                }
                for r in corr_rules
            ],
            use_container_width=True,
        )


def render_timeline(store: EventStore) -> None:
    """Alert timeline visualization."""
    st.subheader("Alert Timeline")
    alerts = store.query_alerts(limit=500)
    if not alerts:
        st.info("No alert data for timeline.")
        return

    times = []
    severities = []
    labels = []
    for a in alerts:
        try:
            times.append(datetime.fromisoformat(a["timestamp"]))
        except (ValueError, TypeError):
            times.append(datetime.now(UTC))
        severities.append(a["severity"])
        labels.append(a.get("rule_title") or a.get("rule_id", "unknown"))

    fig = px.scatter(
        x=times,
        y=severities,
        color=severities,
        hover_name=labels,
        color_discrete_map={
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#28a745",
        },
        labels={"x": "Time", "y": "Severity"},
        title="Alert Timeline",
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    """Dashboard entry point."""
    st.set_page_config(page_title="SIEM SOC Dashboard", page_icon="🛡️", layout="wide")
    st.title("SIEM Detection Engine — SOC Dashboard")

    store = get_store()
    processor = get_processor()

    # Sidebar
    with st.sidebar:
        st.header("Controls")
        if st.button("Generate Sample Data"):
            with st.spinner("Generating..."):
                count = seed_data(store, processor)
            st.success(f"Generated events — {count} alerts detected")
            st.rerun()

        st.divider()
        st.caption(f"DB: {DB_PATH}")
        stats = store.get_stats()
        st.caption(f"Events: {stats['event_count']} | Alerts: {stats['alert_count']}")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Alerts", "Events", "Rules", "Timeline"])
    with tab1:
        render_overview(store, processor)
    with tab2:
        render_alerts(store)
    with tab3:
        render_events(store)
    with tab4:
        render_rules(processor)
    with tab5:
        render_timeline(store)


if __name__ == "__main__":
    main()
