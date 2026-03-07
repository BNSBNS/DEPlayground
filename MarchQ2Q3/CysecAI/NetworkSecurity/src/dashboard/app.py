"""Streamlit dashboard for the Network Security Monitor."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import streamlit as st

st.set_page_config(
    page_title="NetworkSecurity Monitor",
    page_icon="🛡️",
    layout="wide",
)

st.title("NetworkSecurity Monitor — Threat Dashboard")

# ── Sidebar: file upload ───────────────────────────────────────────────────────

with st.sidebar:
    st.header("Analyze Traffic")
    upload_type = st.selectbox(
        "Input type",
        ["Packet JSON", "CloudTrail JSON", "VPC Flow JSON", "K8s Audit JSON"],
    )
    uploaded = st.file_uploader(
        "Upload data file (JSON)",
        type=["json"],
        help="JSON file containing packet records or cloud log events",
    )
    analyze_btn = st.button("Analyze", type="primary")

# ── Load and display ───────────────────────────────────────────────────────────


def _run_analysis(data: list[dict[str, Any]], input_type: str) -> list[dict[str, Any]]:
    """Run the appropriate detectors and return alert dicts."""
    alerts: list[dict[str, Any]] = []
    if input_type == "Packet JSON":
        from src.detection.arp_spoof import ARPSpoofDetector
        from src.detection.beaconing import BeaconingDetector
        from src.detection.brute_force import BruteForceDetector
        from src.detection.cleartext_creds import CleartextCredsDetector
        from src.detection.dns_exfil import DNSExfilDetector
        from src.detection.port_scan import PortScanDetector
        from src.parser.json_loader import load_packets_from_list

        packets = load_packets_from_list(data)
        detectors = [
            PortScanDetector(),
            BruteForceDetector(),
            ARPSpoofDetector(),
            DNSExfilDetector(),
            BeaconingDetector(),
            CleartextCredsDetector(),
        ]
        for det in detectors:
            for alert in det.analyze(packets):
                alerts.append(
                    {
                        "rule": alert.rule_id,
                        "title": alert.title,
                        "severity": str(alert.severity),
                        "mitre": alert.mitre_technique_id,
                        "source_ip": alert.source_ip,
                        "dest_ip": alert.dest_ip or "",
                        "evidence": alert.evidence,
                        "packet_count": alert.packet_count,
                    }
                )
    else:
        source_map = {
            "CloudTrail JSON": ("cloudtrail", "src.cloud.cloudtrail_parser", "parse_cloudtrail"),
            "VPC Flow JSON": ("vpc_flow", "src.cloud.vpc_flow_parser", "parse_vpc_flow_json"),
            "K8s Audit JSON": ("k8s_audit", "src.cloud.k8s_audit_parser", "parse_k8s_audit"),
        }
        _source, module_name, func_name = source_map[input_type]
        import importlib

        module = importlib.import_module(module_name)
        parse_fn = getattr(module, func_name)
        events = parse_fn(data)

        from src.detection.base import BaseCloudDetector  # noqa: TC001
        from src.detection.cloud_detectors import (
            CloudTrailAssumeRoleDetector,
            CloudTrailIAMPrivescDetector,
            CloudTrailLoggingDisabledDetector,
            K8sPrivilegedContainerDetector,
            K8sRBACWildcardDetector,
        )

        cloud_detectors: list[BaseCloudDetector] = [
            K8sPrivilegedContainerDetector(),
            K8sRBACWildcardDetector(),
            CloudTrailIAMPrivescDetector(),
            CloudTrailLoggingDisabledDetector(),
            CloudTrailAssumeRoleDetector(),
        ]
        for cloud_det in cloud_detectors:
            for alert in cloud_det.analyze(events):
                alerts.append(
                    {
                        "rule": alert.rule_id,
                        "title": alert.title,
                        "severity": str(alert.severity),
                        "mitre": alert.mitre_technique_id,
                        "source_ip": alert.source_ip,
                        "dest_ip": alert.dest_ip or "",
                        "evidence": alert.evidence,
                        "packet_count": alert.packet_count,
                    }
                )
    return alerts


if analyze_btn and uploaded is not None:
    raw = json.loads(uploaded.read().decode("utf-8"))
    data_list: list[dict[str, Any]] = raw if isinstance(raw, list) else [raw]
    with st.spinner("Analyzing..."):
        alerts = _run_analysis(data_list, upload_type)
    st.session_state["alerts"] = alerts
    st.session_state["input_count"] = len(data_list)
elif "alerts" not in st.session_state:
    # Load sample data if available
    sample = pathlib.Path("test_data/port_scan.json")
    if sample.exists():
        sample_data = json.loads(sample.read_text(encoding="utf-8"))
        from src.detection.port_scan import PortScanDetector
        from src.parser.json_loader import load_packets_from_list

        packets = load_packets_from_list(sample_data)
        raw_alerts = PortScanDetector().analyze(packets)
        st.session_state["alerts"] = [
            {
                "rule": a.rule_id,
                "title": a.title,
                "severity": str(a.severity),
                "mitre": a.mitre_technique_id,
                "source_ip": a.source_ip,
                "dest_ip": a.dest_ip or "",
                "evidence": a.evidence,
                "packet_count": a.packet_count,
            }
            for a in raw_alerts
        ]
        st.session_state["input_count"] = len(sample_data)
    else:
        st.session_state["alerts"] = []
        st.session_state["input_count"] = 0

alerts_data: list[dict[str, Any]] = st.session_state.get("alerts", [])
input_count: int = st.session_state.get("input_count", 0)

# ── Metrics ────────────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
critical = sum(1 for a in alerts_data if a["severity"] == "CRITICAL")
high = sum(1 for a in alerts_data if a["severity"] == "HIGH")
medium = sum(1 for a in alerts_data if a["severity"] == "MEDIUM")

col1.metric("Input Records", input_count)
col2.metric("Total Alerts", len(alerts_data))
col3.metric("Critical", critical, delta=None if critical == 0 else f"+{critical}")
col4.metric("High", high)

if not alerts_data:
    st.info("No alerts detected. Upload a data file to begin analysis.")
    st.stop()

# ── Severity breakdown ─────────────────────────────────────────────────────────

st.subheader("Severity Breakdown")
import pandas as pd

sev_counts = {
    "CRITICAL": critical,
    "HIGH": high,
    "MEDIUM": medium,
    "LOW": sum(1 for a in alerts_data if a["severity"] == "LOW"),
}
sev_df = pd.DataFrame(list(sev_counts.items()), columns=["Severity", "Count"])
sev_df = sev_df[sev_df["Count"] > 0]
st.bar_chart(sev_df.set_index("Severity"))

# ── Rule breakdown ─────────────────────────────────────────────────────────────

st.subheader("Detections by Rule")
from collections import Counter

rule_counts = Counter(a["rule"] for a in alerts_data)
rule_df = pd.DataFrame(list(rule_counts.items()), columns=["Rule", "Alerts"])
st.bar_chart(rule_df.set_index("Rule"))

# ── Alert table ────────────────────────────────────────────────────────────────

st.subheader("Alert Feed")
sev_filter = st.selectbox(
    "Filter by severity", ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
)
filtered = [a for a in alerts_data if sev_filter == "All" or a["severity"] == sev_filter]
if filtered:
    alert_df = pd.DataFrame(filtered)
    st.dataframe(alert_df, use_container_width=True)

    st.subheader("Alert Detail")
    titles = [f"[{a['severity']}] {a['title']} — {a['source_ip']}" for a in filtered]
    selected_idx = st.selectbox("Select alert", range(len(titles)), format_func=lambda i: titles[i])
    selected = filtered[selected_idx]
    st.markdown(f"**Rule:** `{selected['rule']}`")
    st.markdown(f"**MITRE:** `{selected['mitre']}`")
    st.markdown(f"**Source:** `{selected['source_ip']}`")
    if selected["dest_ip"]:
        st.markdown(f"**Destination:** `{selected['dest_ip']}`")
    st.markdown(f"**Evidence:** {selected['evidence']}")
else:
    st.info(f"No {sev_filter} alerts.")
