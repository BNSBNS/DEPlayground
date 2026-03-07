"""Graph loader — MERGE-based upsert of TIKG nodes and relationships to Neo4j."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.graph.schema import (
    CONSTRAINTS,
    INDEXES,
    LABEL_ATTACK_TECHNIQUE,
    LABEL_CVE,
    LABEL_CWE,
    LABEL_KEV_ENTRY,
    LABEL_SOFTWARE,
    REL_AFFECTS,
    REL_EXPLOITED_BY,
    REL_EXPLOITS,
    REL_HAS_WEAKNESS,
)
from src.models import CVE, CWE, AttackTechnique, KEVEntry, Software

if TYPE_CHECKING:
    from neo4j import AsyncDriver, AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cypher helpers
# ---------------------------------------------------------------------------

_MERGE_CVE = f"""
MERGE (n:{LABEL_CVE} {{cve_id: $cve_id}})
SET n.description = $description,
    n.published = $published,
    n.last_modified = $last_modified,
    n.severity = $severity,
    n.base_score = $base_score,
    n.epss_score = $epss_score
"""

_MERGE_CWE = f"""
MERGE (n:{LABEL_CWE} {{cwe_id: $cwe_id}})
SET n.name = $name, n.description = $description
"""

_MERGE_TECHNIQUE = f"""
MERGE (n:{LABEL_ATTACK_TECHNIQUE} {{technique_id: $technique_id}})
SET n.name = $name, n.description = $description,
    n.tactic = $tactic, n.platforms = $platforms
"""

_MERGE_SOFTWARE = f"""
MERGE (n:{LABEL_SOFTWARE} {{node_id: $node_id}})
SET n.vendor = $vendor, n.product = $product, n.version = $version
"""

_MERGE_KEV = f"""
MERGE (n:{LABEL_KEV_ENTRY} {{cve_id: $cve_id}})
SET n.vendor_project = $vendor_project, n.product = $product,
    n.vulnerability_name = $vulnerability_name,
    n.date_added = $date_added, n.required_action = $required_action
"""

_REL_CVE_CWE = f"""
MATCH (c:{LABEL_CVE} {{cve_id: $cve_id}})
MATCH (w:{LABEL_CWE} {{cwe_id: $cwe_id}})
MERGE (c)-[:{REL_HAS_WEAKNESS}]->(w)
"""

_REL_CVE_SOFTWARE = f"""
MATCH (c:{LABEL_CVE} {{cve_id: $cve_id}})
MATCH (s:{LABEL_SOFTWARE} {{node_id: $node_id}})
MERGE (c)-[:{REL_AFFECTS}]->(s)
"""

_REL_CVE_KEV = f"""
MATCH (c:{LABEL_CVE} {{cve_id: $cve_id}})
MATCH (k:{LABEL_KEV_ENTRY} {{cve_id: $cve_id}})
MERGE (c)-[:{REL_EXPLOITED_BY}]->(k)
"""

_REL_TECHNIQUE_CVE = f"""
MATCH (t:{LABEL_ATTACK_TECHNIQUE} {{technique_id: $technique_id}})
MATCH (c:{LABEL_CVE} {{cve_id: $cve_id}})
MERGE (t)-[:{REL_EXPLOITS}]->(c)
"""


# ---------------------------------------------------------------------------
# GraphLoader
# ---------------------------------------------------------------------------


class GraphLoader:
    """Loads TIKG domain objects into Neo4j using MERGE upsert semantics."""

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    async def _run(self, session: AsyncSession, query: str, **params: Any) -> None:
        await session.run(query, **params)

    async def apply_schema(self) -> None:
        """Apply Neo4j constraints and indexes."""
        async with self._driver.session(database=self._database) as session:
            for stmt in CONSTRAINTS:
                await self._run(session, stmt)
            for stmt in INDEXES:
                await self._run(session, stmt)
        logger.info("Schema applied: %d constraints, %d indexes", len(CONSTRAINTS), len(INDEXES))

    async def load_cve(self, cve: CVE) -> None:
        """Upsert a CVE node and its relationships."""
        async with self._driver.session(database=self._database) as session:
            await self._run(
                session,
                _MERGE_CVE,
                cve_id=cve.cve_id,
                description=cve.description,
                published=cve.published.isoformat(),
                last_modified=cve.last_modified.isoformat(),
                severity=cve.severity,
                base_score=cve.base_score,
                epss_score=cve.epss_score,
            )
            for cwe_id in cve.cwe_ids:
                await self._run(
                    session,
                    _MERGE_CWE,
                    cwe_id=cwe_id,
                    name="",
                    description="",
                )
                await self._run(session, _REL_CVE_CWE, cve_id=cve.cve_id, cwe_id=cwe_id)
            for match in cve.cpe_matches:
                parts = match.cpe_name.split(":")
                vendor = parts[3] if len(parts) > 3 else "unknown"
                product = parts[4] if len(parts) > 4 else "unknown"
                version = parts[5] if len(parts) > 5 and parts[5] != "*" else None
                sw = Software(vendor=vendor, product=product, version=version)
                await self.load_software(sw)
                await self._run(session, _REL_CVE_SOFTWARE, cve_id=cve.cve_id, node_id=sw.node_id)

    async def load_cve_batch(self, cves: list[CVE]) -> None:
        """Load a list of CVEs."""
        for cve in cves:
            await self.load_cve(cve)
        logger.info("Loaded %d CVEs", len(cves))

    async def load_cwe(self, cwe: CWE) -> None:
        """Upsert a CWE node."""
        async with self._driver.session(database=self._database) as session:
            await self._run(
                session,
                _MERGE_CWE,
                cwe_id=cwe.cwe_id,
                name=cwe.name,
                description=cwe.description,
            )

    async def load_technique(self, technique: AttackTechnique) -> None:
        """Upsert an ATT&CK technique node."""
        async with self._driver.session(database=self._database) as session:
            await self._run(
                session,
                _MERGE_TECHNIQUE,
                technique_id=technique.technique_id,
                name=technique.name,
                description=technique.description,
                tactic=technique.tactic,
                platforms=technique.platforms,
            )

    async def load_software(self, software: Software) -> None:
        """Upsert a Software node."""
        async with self._driver.session(database=self._database) as session:
            await self._run(
                session,
                _MERGE_SOFTWARE,
                node_id=software.node_id,
                vendor=software.vendor,
                product=software.product,
                version=software.version,
            )

    async def load_kev(self, kev: KEVEntry) -> None:
        """Upsert a KEV entry node and link to its CVE."""
        async with self._driver.session(database=self._database) as session:
            await self._run(
                session,
                _MERGE_KEV,
                cve_id=kev.cve_id,
                vendor_project=kev.vendor_project,
                product=kev.product,
                vulnerability_name=kev.vulnerability_name,
                date_added=kev.date_added.isoformat(),
                required_action=kev.required_action,
            )
            await self._run(session, _REL_CVE_KEV, cve_id=kev.cve_id)

    async def link_technique_cve(self, technique_id: str, cve_id: str) -> None:
        """Create an EXPLOITS relationship between a technique and a CVE."""
        async with self._driver.session(database=self._database) as session:
            await self._run(session, _REL_TECHNIQUE_CVE, technique_id=technique_id, cve_id=cve_id)
