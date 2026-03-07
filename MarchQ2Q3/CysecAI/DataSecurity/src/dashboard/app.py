"""Streamlit compliance dashboard for DataSecurity."""

from __future__ import annotations

import json

import streamlit as st

st.set_page_config(
    page_title="DataSecurity — Compliance Dashboard",
    page_icon="🔒",
    layout="wide",
)

st.title("🔒 DataSecurity — Compliance Dashboard")
st.caption("PII discovery, encryption auditing, and compliance reporting.")

# ── Sidebar: database connection ──────────────────────────────────────────────
st.sidebar.header("Database Connection")
db_url = st.sidebar.text_input(
    "SQLite URL",
    value="sqlite:///:memory:",
    help="Enter a SQLite URL. PostgreSQL/MySQL require the CLI.",
)
frameworks = st.sidebar.multiselect(
    "Frameworks",
    ["PDPA", "GDPR", "PCI-DSS"],
    default=["PDPA", "GDPR", "PCI-DSS"],
)
scan_btn = st.sidebar.button("Run Scan", type="primary")

if not scan_btn:
    st.info("Configure a database URL in the sidebar and click **Run Scan**.")
    st.stop()

# ── Run scan ──────────────────────────────────────────────────────────────────
with st.spinner("Scanning database..."):
    from src.audit.tde_checker import check_tde
    from src.compliance.report_generator import generate_report
    from src.db.sqlite_adapter import SQLiteAdapter
    from src.discovery.schema_scanner import scan_schema

    adapter = SQLiteAdapter(db_url)
    tables = scan_schema(adapter)
    encryption = check_tde(adapter)
    report = generate_report(tables, encryption, frameworks=frameworks or ["PDPA"])

# ── Summary metrics ──────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Tables Scanned", len(report.tables_scanned))
col2.metric("PII Columns", report.pii_columns_found)
col3.metric("TDE", "ON" if report.tde_enabled else "OFF")
col4.metric("TLS", "ON" if report.tls_enabled else "OFF")
col5.metric("Risk Score", f"{report.risk_score:.0%}")

# ── Compliance requirements table ─────────────────────────────────────────────
st.subheader("Compliance Requirements")

import pandas as pd

rows = [
    {
        "ID": r.requirement_id,
        "Framework": r.framework,
        "Article": r.article,
        "Description": r.description[:80],
        "Status": str(r.status),
    }
    for r in report.requirements
]
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

# ── PII columns ───────────────────────────────────────────────────────────────
st.subheader("PII Columns Detected")
pii_tables = [t for t in tables if t.has_pii]

if pii_tables:
    pii_rows = [
        {
            "Table": c.table_name,
            "Column": c.column_name,
            "Classification": str(c.classification),
            "PII Types": ", ".join(str(p) for p in c.pii_types),
            "Masking": str(c.masking_strategy),
        }
        for t in pii_tables
        for c in t.pii_columns
    ]
    st.dataframe(pd.DataFrame(pii_rows), use_container_width=True)
else:
    st.success("No PII columns detected in this database.")

# ── Failures detail ───────────────────────────────────────────────────────────
failures = [r for r in report.requirements if str(r.status) == "FAIL"]
if failures:
    st.subheader("Failures & Remediations")
    for r in failures:
        with st.expander(f"{r.requirement_id} — {r.description[:60]}"):
            st.write("**Findings:**")
            for f in r.findings:
                st.write(f"- {f}")
            if r.remediation:
                st.write(f"**Remediation:** {r.remediation}")

# ── JSON export ───────────────────────────────────────────────────────────────
st.subheader("Export Report")
report_json = json.dumps(report.to_dict(), indent=2)
st.download_button(
    label="Download JSON Report",
    data=report_json,
    file_name=f"compliance_{report.database_name}.json",
    mime="application/json",
)
