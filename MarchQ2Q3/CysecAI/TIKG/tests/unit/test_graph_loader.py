"""Tests for GraphLoader — Neo4j driver is fully mocked."""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.graph.loader import GraphLoader
from src.graph.schema import CONSTRAINTS, INDEXES
from src.models import CVE, CWE, AttackTechnique, CPEMatch, CVSSScore, KEVEntry, Software

_UTC = datetime.UTC
_DT = datetime.datetime


# ---------------------------------------------------------------------------
# Mock driver factory
# ---------------------------------------------------------------------------


def _make_driver() -> tuple[MagicMock, MagicMock]:
    """Return (mock_driver, mock_session)."""
    mock_session = AsyncMock()
    mock_session.run = AsyncMock()

    @asynccontextmanager  # type: ignore[misc]
    async def _session_ctx(*_: Any, **__: Any) -> Any:
        yield mock_session

    mock_driver = MagicMock()
    mock_driver.session = _session_ctx
    return mock_driver, mock_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def driver_and_session() -> tuple[MagicMock, MagicMock]:
    return _make_driver()


@pytest.fixture()
def loader(driver_and_session: tuple[MagicMock, MagicMock]) -> GraphLoader:
    driver, _ = driver_and_session
    return GraphLoader(driver)


@pytest.fixture()
def sample_cve() -> CVE:
    return CVE(
        cve_id="CVE-2024-12345",
        description="Test RCE",
        published=_DT(2024, 1, 1, tzinfo=_UTC),
        last_modified=_DT(2024, 2, 1, tzinfo=_UTC),
        cvss_v3=CVSSScore(version="3.1", base_score=9.8, severity="CRITICAL"),
        cwe_ids=["CWE-79"],
    )


@pytest.fixture()
def sample_cve_with_cpe() -> CVE:
    return CVE(
        cve_id="CVE-2024-99999",
        description="Test CPE RCE",
        published=_DT(2024, 1, 1, tzinfo=_UTC),
        last_modified=_DT(2024, 2, 1, tzinfo=_UTC),
        cpe_matches=[
            CPEMatch(
                cpe_name="cpe:2.3:a:apache:log4j:2.14.0:*:*:*:*:*:*:*",
                version_end_excluding="2.15.0",
            )
        ],
    )


@pytest.fixture()
def sample_kev() -> KEVEntry:
    return KEVEntry(
        cve_id="CVE-2024-12345",
        vendor_project="Acme",
        product="Widget",
        vulnerability_name="Widget RCE",
        date_added=_DT(2024, 2, 1, tzinfo=_UTC),
        short_description="RCE in Widget.",
        required_action="Apply patch.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplySchema:
    @pytest.mark.asyncio
    async def test_applies_all_constraints_and_indexes(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock]
    ) -> None:
        _, session = driver_and_session
        await loader.apply_schema()
        expected_calls = len(CONSTRAINTS) + len(INDEXES)
        assert session.run.call_count == expected_calls

    @pytest.mark.asyncio
    async def test_constraint_queries_are_run(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock]
    ) -> None:
        _, session = driver_and_session
        await loader.apply_schema()
        calls = [str(c) for c in session.run.call_args_list]
        assert any("CREATE CONSTRAINT" in c for c in calls)


class TestLoadCVE:
    @pytest.mark.asyncio
    async def test_load_cve_basic(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock], sample_cve: CVE
    ) -> None:
        _, session = driver_and_session
        await loader.load_cve(sample_cve)
        # Should call: MERGE CVE + MERGE CWE + REL CVE-CWE (at minimum)
        assert session.run.call_count >= 3

    @pytest.mark.asyncio
    async def test_load_cve_with_cpe(
        self,
        loader: GraphLoader,
        driver_and_session: tuple[MagicMock, MagicMock],
        sample_cve_with_cpe: CVE,
    ) -> None:
        _, session = driver_and_session
        await loader.load_cve(sample_cve_with_cpe)
        # CVE MERGE + Software MERGE + CVE-Software REL
        assert session.run.call_count >= 3

    @pytest.mark.asyncio
    async def test_load_cve_batch(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock], sample_cve: CVE
    ) -> None:
        _, session = driver_and_session
        cves = [sample_cve]
        await loader.load_cve_batch(cves)
        assert session.run.call_count >= 1


class TestLoadCWE:
    @pytest.mark.asyncio
    async def test_load_cwe(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock]
    ) -> None:
        _, session = driver_and_session
        cwe = CWE(cwe_id="CWE-79", name="XSS", description="Cross-site scripting.")
        await loader.load_cwe(cwe)
        session.run.assert_called_once()
        args = session.run.call_args
        assert "CWE-79" in str(args)


class TestLoadTechnique:
    @pytest.mark.asyncio
    async def test_load_technique(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock]
    ) -> None:
        _, session = driver_and_session
        tech = AttackTechnique(
            technique_id="T1059",
            name="Command Execution",
            description="Execute commands.",
            tactic="execution",
            platforms=["Windows"],
        )
        await loader.load_technique(tech)
        session.run.assert_called_once()
        args = session.run.call_args
        assert "T1059" in str(args)


class TestLoadSoftware:
    @pytest.mark.asyncio
    async def test_load_software(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock]
    ) -> None:
        _, session = driver_and_session
        sw = Software(vendor="apache", product="log4j", version="2.14.0")
        await loader.load_software(sw)
        session.run.assert_called_once()
        args = session.run.call_args
        assert "apache:log4j:2.14.0" in str(args)


class TestLoadKEV:
    @pytest.mark.asyncio
    async def test_load_kev(
        self,
        loader: GraphLoader,
        driver_and_session: tuple[MagicMock, MagicMock],
        sample_kev: KEVEntry,
    ) -> None:
        _, session = driver_and_session
        await loader.load_kev(sample_kev)
        # MERGE KEV + REL CVE-KEV
        assert session.run.call_count == 2

    @pytest.mark.asyncio
    async def test_link_technique_cve(
        self, loader: GraphLoader, driver_and_session: tuple[MagicMock, MagicMock]
    ) -> None:
        _, session = driver_and_session
        await loader.link_technique_cve("T1059", "CVE-2024-12345")
        session.run.assert_called_once()
        args = session.run.call_args
        assert "T1059" in str(args)
        assert "CVE-2024-12345" in str(args)
