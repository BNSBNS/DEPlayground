"""Streamlit dashboard — TIKG Threat Intelligence Knowledge Graph."""

from __future__ import annotations

import streamlit as st

from src.config import TIKGSettings
from src.query_engine.nl_to_cypher import NLQueryEngine

st.set_page_config(
    page_title="Threat Intelligence Knowledge Graph",
    page_icon="🕸️",
    layout="wide",
)


@st.cache_resource
def get_engine() -> NLQueryEngine:
    return NLQueryEngine()


@st.cache_resource
def get_settings() -> TIKGSettings:
    return TIKGSettings()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🕸️ Threat Intelligence Knowledge Graph")
st.caption("Query CVEs, ATT&CK techniques, KEV, and software relationships")

tab_query, tab_explore, tab_config = st.tabs(["NL Query", "Explorer", "Config"])

# ── Tab 1: NL-to-Cypher ────────────────────────────────────────────────────
with tab_query:
    st.header("Natural Language Query")
    st.write("Ask questions about the knowledge graph in plain English.")

    examples = {
        "Show CVE-2021-44228 details": "Show me CVE-2021-44228",
        "Top 10 critical CVEs": "Show top 10 most critical CVEs by base score",
        "KEV catalog entries": "Which CVEs are in the CISA KEV catalog?",
        "Apache vulnerabilities": "CVEs affecting Apache software",
        "Execution techniques": "Show ATT&CK techniques for execution tactic",
        "High EPSS CVEs": "CVEs with high EPSS exploitation probability",
    }

    selected_example = st.selectbox("Quick examples", ["(custom)", *list(examples.keys())])
    question = st.text_input(
        "Your question",
        value=examples.get(selected_example, "") if selected_example != "(custom)" else "",
        placeholder="e.g. Show me CVE-2021-44228 details",
    )

    if st.button("Translate to Cypher", type="primary") and question.strip():
        engine = get_engine()
        result = engine.translate(question)

        col1, col2 = st.columns(2)
        col1.metric("Intent", result.intent.replace("_", " ").title())
        col2.metric("Confidence", f"{result.confidence:.0%}")

        st.subheader("Generated Cypher")
        st.code(result.cypher, language="cypher")

        if result.parameters:
            st.subheader("Query Parameters")
            st.json(result.parameters)

        st.caption("Connect to Neo4j and run this query to retrieve results.")

# ── Tab 2: Explorer ─────────────────────────────────────────────────────────
with tab_explore:
    st.header("Graph Explorer")
    st.write("Explore the knowledge graph schema and sample Cypher queries.")

    st.subheader("Node Types")
    nodes = {
        "CVE": "National Vulnerability Database entries with CVSS scores",
        "CWE": "Common Weakness Enumeration entries",
        "AttackTechnique": "MITRE ATT&CK techniques",
        "Software": "Affected software/vendor nodes",
        "KEVEntry": "CISA Known Exploited Vulnerabilities",
    }
    for label, desc in nodes.items():
        st.write(f"**:{label}** — {desc}")

    st.divider()
    st.subheader("Relationships")
    rels = {
        "HAS_WEAKNESS": "CVE → CWE (vulnerability class)",
        "AFFECTS": "CVE → Software (impacted products)",
        "EXPLOITED_BY": "CVE → KEVEntry (actively exploited)",
        "EXPLOITS": "AttackTechnique → CVE (exploitation linkage)",
    }
    for rel, desc in rels.items():
        st.write(f"**[{rel}]** — {desc}")

    st.divider()
    st.subheader("Sample Cypher Queries")
    samples = [
        (
            "Top 10 critical CVEs",
            "MATCH (c:CVE) WHERE c.severity = 'CRITICAL' "
            "RETURN c ORDER BY c.base_score DESC LIMIT 10",
        ),
        (
            "KEV entries this year",
            "MATCH (c:CVE)-[:EXPLOITED_BY]->(k:KEVEntry) "
            "RETURN c.cve_id, k.date_added ORDER BY k.date_added DESC LIMIT 20",
        ),
        (
            "Apache CVEs",
            "MATCH (c:CVE)-[:AFFECTS]->(s:Software) "
            "WHERE toLower(s.vendor) = 'apache' RETURN c, s LIMIT 10",
        ),
    ]
    for title, cypher in samples:
        with st.expander(title):
            st.code(cypher, language="cypher")

# ── Tab 3: Config ────────────────────────────────────────────────────────────
with tab_config:
    st.header("Configuration")
    settings = get_settings()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Neo4j")
        st.write(f"**URI:** `{settings.neo4j.uri}`")
        st.write(f"**User:** `{settings.neo4j.user}`")
        st.write(f"**Database:** `{settings.neo4j.database}`")

    with col2:
        st.subheader("NVD API")
        st.write(f"**Base URL:** `{settings.nvd.base_url}`")
        st.write(f"**Results/page:** `{settings.nvd.results_per_page}`")
        st.write(f"**Rate limit delay:** `{settings.nvd.rate_limit_delay}s`")
        api_status = "Configured" if settings.nvd.api_key else "Not set (6 req/min limit)"
        st.write(f"**API Key:** {api_status}")
