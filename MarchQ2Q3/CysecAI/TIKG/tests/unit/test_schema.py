"""Tests for Neo4j schema constants."""

from __future__ import annotations

from src.graph.schema import (
    CONSTRAINTS,
    INDEXES,
    LABEL_CVE,
    LABEL_CWE,
    REL_AFFECTS,
    REL_EXPLOITED_BY,
    REL_HAS_WEAKNESS,
)


def test_constraints_are_cypher_strings() -> None:
    assert len(CONSTRAINTS) >= 5
    for stmt in CONSTRAINTS:
        assert "CREATE CONSTRAINT" in stmt
        assert "IF NOT EXISTS" in stmt


def test_indexes_are_cypher_strings() -> None:
    assert len(INDEXES) >= 4
    for stmt in INDEXES:
        assert "CREATE" in stmt
        assert "IF NOT EXISTS" in stmt


def test_labels_defined() -> None:
    assert LABEL_CVE == "CVE"
    assert LABEL_CWE == "CWE"


def test_relationships_defined() -> None:
    assert REL_HAS_WEAKNESS == "HAS_WEAKNESS"
    assert REL_AFFECTS == "AFFECTS"
    assert REL_EXPLOITED_BY == "EXPLOITED_BY"
