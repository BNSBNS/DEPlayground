"""Streamlit dashboard for the APISecurity Scanner."""

from __future__ import annotations

import httpx
import pandas as pd
import streamlit as st

_API_URL = "http://localhost:8002"
_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
_SEVERITY_COLORS = {
    "CRITICAL": "#d62728",
    "HIGH": "#ff7f0e",
    "MEDIUM": "#ffbb78",
    "LOW": "#98df8a",
    "INFO": "#aec7e8",
}

st.set_page_config(
    page_title="APISecurity Scanner",
    page_icon="🔒",
    layout="wide",
)
st.title("APISecurity Scanner — OWASP API Top 10")

# ── Sidebar: submit scan ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("New Scan")
    target = st.text_input("Target URL", value="http://localhost:8001")
    timeout = st.slider("Timeout (s)", min_value=5, max_value=60, value=10)

    if st.button("Run Scan", type="primary"):
        with st.spinner("Scan in progress…"):
            try:
                submit = httpx.post(
                    f"{_API_URL}/api/v1/scans",
                    json={"target_url": target, "timeout": timeout},
                    timeout=5,
                )
                if submit.status_code == 202:
                    scan_id = submit.json()["scan_id"]
                    # Poll until complete (simple blocking poll for dashboard)
                    import time

                    for _ in range(60):
                        time.sleep(2)
                        status_resp = httpx.get(f"{_API_URL}/api/v1/scans/{scan_id}", timeout=5)
                        data = status_resp.json()
                        if data.get("status") not in ("pending", "running"):
                            break
                    st.session_state["scan_data"] = data
                    st.success(f"Scan complete — {data.get('finding_count', 0)} findings")
                else:
                    st.error(f"Submit failed: HTTP {submit.status_code}")
            except httpx.ConnectError:
                st.error(f"Cannot reach API at {_API_URL}")

    st.divider()

    st.header("Recent Scans")
    try:
        recent = httpx.get(f"{_API_URL}/api/v1/scans", timeout=5)
        if recent.status_code == 200:
            for scan in recent.json()[:5]:
                label = f"{scan['status']} — {scan['target_url'][:30]}"
                if st.button(label, key=scan["scan_id"]):
                    detail = httpx.get(f"{_API_URL}/api/v1/scans/{scan['scan_id']}", timeout=5)
                    if detail.status_code == 200:
                        st.session_state["scan_data"] = detail.json()
    except httpx.ConnectError:
        st.caption("API unavailable")

# ── Main: display scan results ────────────────────────────────────────────────

if "scan_data" not in st.session_state:
    st.info("Submit a scan from the sidebar to see results.")
    st.stop()

scan = st.session_state["scan_data"]

if scan.get("status") in ("pending", "running"):
    st.warning(f"Scan status: {scan['status']} — refresh to update")
    st.stop()

if scan.get("status") == "error":
    st.error(f"Scan failed: {scan.get('error', 'unknown error')}")
    st.stop()

# ── Metrics ───────────────────────────────────────────────────────────────────

st.subheader(f"Results — {scan.get('target_url', '')}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Findings", scan.get("finding_count", 0))
c2.metric("Critical", scan.get("critical_count", 0), delta_color="inverse")
c3.metric("High", scan.get("high_count", 0), delta_color="inverse")
c4.metric("Endpoints Scanned", scan.get("endpoints_scanned", 0))
c5.metric("Scan ID", scan.get("scan_id", "")[:8] + "…")

findings = scan.get("findings", [])
if not findings:
    st.success("No findings — the target looks clean!")
    st.stop()

df = pd.DataFrame(findings)

# ── Charts ────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Findings by Severity")
    sev_counts = (
        df["severity"]
        .value_counts()
        .reindex([s for s in _SEVERITY_ORDER if s in df["severity"].unique()], fill_value=0)
    )
    st.bar_chart(sev_counts)

with col_right:
    st.subheader("Findings by OWASP Category")
    cat_counts = df["owasp_category"].value_counts()
    st.bar_chart(cat_counts)

# ── Findings table ────────────────────────────────────────────────────────────

st.subheader("All Findings")

severity_filter = st.multiselect(
    "Filter by Severity",
    options=_SEVERITY_ORDER,
    default=_SEVERITY_ORDER,
)
filtered = df[df["severity"].isin(severity_filter)] if severity_filter else df

st.dataframe(
    filtered[["severity", "owasp_category", "title", "endpoint", "method"]],
    use_container_width=True,
)

# ── Finding detail ────────────────────────────────────────────────────────────

if not filtered.empty:
    st.subheader("Finding Detail")
    titles = filtered["title"].tolist()
    selected = st.selectbox("Select finding", options=titles)
    if selected:
        row = filtered[filtered["title"] == selected].iloc[0]
        st.markdown(f"**Severity:** {row['severity']}")
        st.markdown(f"**Category:** {row['owasp_category']}")
        st.markdown(f"**Endpoint:** `{row['method']} {row['endpoint']}`")
        st.markdown(f"**Evidence:**\n\n{row['evidence']}")
        st.markdown(f"**Remediation:**\n\n{row['remediation']}")
