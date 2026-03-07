"""Neo4j schema — constraint and index definitions for TIKG."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constraint Cypher statements
# ---------------------------------------------------------------------------

CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT cve_id_unique IF NOT EXISTS FOR (n:CVE) REQUIRE n.cve_id IS UNIQUE",
    "CREATE CONSTRAINT cwe_id_unique IF NOT EXISTS FOR (n:CWE) REQUIRE n.cwe_id IS UNIQUE",
    (
        "CREATE CONSTRAINT technique_id_unique IF NOT EXISTS"
        " FOR (n:AttackTechnique) REQUIRE n.technique_id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT software_id_unique IF NOT EXISTS"
        " FOR (n:Software) REQUIRE n.node_id IS UNIQUE"
    ),
    "CREATE CONSTRAINT kev_cve_id_unique IF NOT EXISTS FOR (n:KEVEntry) REQUIRE n.cve_id IS UNIQUE",
]

# ---------------------------------------------------------------------------
# Index Cypher statements
# ---------------------------------------------------------------------------

INDEXES: list[str] = [
    "CREATE INDEX cve_severity IF NOT EXISTS FOR (n:CVE) ON (n.severity)",
    "CREATE INDEX cve_published IF NOT EXISTS FOR (n:CVE) ON (n.published)",
    "CREATE INDEX cve_base_score IF NOT EXISTS FOR (n:CVE) ON (n.base_score)",
    "CREATE INDEX technique_tactic IF NOT EXISTS FOR (n:AttackTechnique) ON (n.tactic)",
    "CREATE FULLTEXT INDEX cve_description IF NOT EXISTS FOR (n:CVE) ON EACH [n.description]",
]

# ---------------------------------------------------------------------------
# Node labels
# ---------------------------------------------------------------------------

LABEL_CVE = "CVE"
LABEL_CWE = "CWE"
LABEL_ATTACK_TECHNIQUE = "AttackTechnique"
LABEL_SOFTWARE = "Software"
LABEL_KEV_ENTRY = "KEVEntry"

# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------

REL_HAS_WEAKNESS = "HAS_WEAKNESS"  # CVE → CWE
REL_AFFECTS = "AFFECTS"  # CVE → Software
REL_EXPLOITS = "EXPLOITS"  # AttackTechnique → CVE
REL_EXPLOITED_BY = "EXPLOITED_BY"  # CVE → KEVEntry
REL_MITIGATES = "MITIGATES"  # CWE → AttackTechnique
