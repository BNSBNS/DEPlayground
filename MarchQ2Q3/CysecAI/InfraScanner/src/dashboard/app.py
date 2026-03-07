"""Streamlit dashboard for InfraScanner."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import streamlit as st

st.set_page_config(
    page_title="InfraScanner",
    page_icon="🔍",
    layout="wide",
)

st.title("InfraScanner — Supply Chain Security Dashboard")

# ── Sidebar: file uploads ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("Scan a Project")
    uploaded_files = st.file_uploader(
        "Upload manifest files",
        type=["txt", "toml", "json", "mod"],
        accept_multiple_files=True,
        help="Upload requirements.txt, pyproject.toml, package.json, go.mod, or Dockerfile",
    )
    file_type_map: dict[str, str] = {}
    for uf in uploaded_files or []:
        name = uf.name.lower()
        if name.endswith("requirements.txt"):
            file_type_map[uf.name] = "pip_requirements"
        elif name.endswith("pyproject.toml"):
            file_type_map[uf.name] = "pyproject"
        elif name.endswith("package.json"):
            file_type_map[uf.name] = "package_json"
        elif name.endswith("go.mod"):
            file_type_map[uf.name] = "go_mod"
        elif name == "dockerfile":
            file_type_map[uf.name] = "dockerfile"
        else:
            file_type_map[uf.name] = "pip_requirements"  # default

    scan_btn = st.button("Scan", type="primary")

# ── Scanning ───────────────────────────────────────────────────────────────────


def _run_scan(files: list[Any]) -> Any:
    from src.models import Dependency, ScanResult
    from src.parsers.go_parser import parse_go_mod
    from src.parsers.npm_parser import parse_package_json
    from src.parsers.pip_parser import parse_pyproject, parse_requirements
    from src.scanners.docker_scanner import scan_dockerfile
    from src.scanners.typosquat_detector import detect_typosquats
    from src.vuln_db.matcher import match_vulnerabilities
    from src.vuln_db.osv_client import OSVClient

    all_deps: list[Dependency] = []
    docker_content = ""
    result = ScanResult(target_path="dashboard upload")

    for uf in files:
        content = uf.read().decode("utf-8")
        ftype = file_type_map.get(uf.name, "pip_requirements")
        if ftype == "pip_requirements":
            all_deps.extend(parse_requirements(content, source_file=uf.name))
        elif ftype == "pyproject":
            all_deps.extend(parse_pyproject(content, source_file=uf.name))
        elif ftype == "package_json":
            all_deps.extend(parse_package_json(content, source_file=uf.name))
        elif ftype == "go_mod":
            all_deps.extend(parse_go_mod(content, source_file=uf.name))
        elif ftype == "dockerfile":
            docker_content = content

    result.dependencies = all_deps
    result.findings = asyncio.run(match_vulnerabilities(all_deps, OSVClient()))
    result.typosquat_findings = detect_typosquats(all_deps)
    if docker_content:
        result.docker_findings = scan_dockerfile(docker_content)
    return result


if scan_btn and uploaded_files:
    with st.spinner("Scanning..."):
        scan_result = _run_scan(uploaded_files)
    st.session_state["scan_result"] = scan_result
elif "scan_result" not in st.session_state:
    st.info("Upload manifest files and click Scan to begin.")
    st.stop()

result = st.session_state.get("scan_result")
if result is None:
    st.stop()

# ── Metrics ────────────────────────────────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Dependencies", len(result.dependencies))
col2.metric("Vulnerabilities", result.total_vulns)
col3.metric("Critical", result.critical_count)
col4.metric("High", result.high_count)
col5.metric("Docker Issues", len(result.docker_findings))

if result.total_vulns == 0 and not result.docker_findings:
    st.success("No vulnerabilities found.")

# ── Vuln findings table ────────────────────────────────────────────────────────

if result.findings:
    st.subheader("Vulnerability Findings")
    import pandas as pd

    rows = [
        {
            "Package": f.dependency.name,
            "Version": f.dependency.version or "?",
            "Ecosystem": str(f.dependency.ecosystem),
            "CVE": v.vuln_id,
            "Severity": str(v.severity),
            "CVSS": v.cvss_score,
            "Risk Score": f.risk_score,
        }
        for f in result.findings
        for v in f.vulnerabilities
    ]
    df = pd.DataFrame(rows).sort_values("Risk Score", ascending=False)
    st.dataframe(df, use_container_width=True)

# ── Docker findings ────────────────────────────────────────────────────────────

if result.docker_findings:
    st.subheader("Docker Security Issues")
    docker_rows = [
        {
            "Check": d.check_id,
            "Severity": str(d.severity),
            "Line": d.line_number,
            "Description": d.description,
            "Recommendation": d.recommendation,
        }
        for d in result.docker_findings
    ]
    import pandas as pd

    st.dataframe(pd.DataFrame(docker_rows), use_container_width=True)

# ── Typosquat findings ─────────────────────────────────────────────────────────

if result.typosquat_findings:
    st.subheader("Potential Typosquatting")
    typo_rows = [
        {
            "Package": t.package,
            "Similar To": t.similar_to,
            "Distance": t.distance,
            "Ecosystem": str(t.ecosystem),
        }
        for t in result.typosquat_findings
    ]
    import pandas as pd

    st.dataframe(pd.DataFrame(typo_rows), use_container_width=True)

# ── SBOM download ──────────────────────────────────────────────────────────────

st.subheader("SBOM Download")
from src.sbom.cyclonedx_generator import generate_sbom_from_deps

sbom = generate_sbom_from_deps(result.dependencies)
st.download_button(
    "Download CycloneDX SBOM (JSON)",
    data=json.dumps(sbom, indent=2),
    file_name="bom.json",
    mime="application/json",
)
