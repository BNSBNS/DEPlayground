"""Tests for text search on the IngestionStore."""

from __future__ import annotations

import pytest

from src.ingestion.store import IngestionStore


def text_search(store: IngestionStore, query: str) -> list[dict]:
    """Search nodes by name or description (case-insensitive substring)."""
    q = query.lower()
    return [
        node
        for node in store.nodes.values()
        if q in node.get("name", "").lower()
        or q in node.get("description", "").lower()
    ]


class TestTextSearch:
    def test_match_by_name(self, populated_store: IngestionStore) -> None:
        results = text_search(populated_store, "orders_mart")
        assert len(results) == 1
        assert results[0]["name"] == "orders_mart"

    def test_match_by_description(self, populated_store: IngestionStore) -> None:
        results = text_search(populated_store, "dimension")
        assert len(results) == 1
        assert results[0]["name"] == "customers_mart"

    def test_case_insensitive(self, populated_store: IngestionStore) -> None:
        results_lower = text_search(populated_store, "orders_mart")
        results_upper = text_search(populated_store, "ORDERS_MART")
        results_mixed = text_search(populated_store, "Orders_Mart")
        assert len(results_lower) == len(results_upper) == len(results_mixed) == 1

    def test_no_results(self, populated_store: IngestionStore) -> None:
        results = text_search(populated_store, "nonexistent_xyz_table")
        assert results == []

    def test_partial_match(self, populated_store: IngestionStore) -> None:
        results = text_search(populated_store, "mart")
        names = {r["name"] for r in results}
        assert "orders_mart" in names
        assert "customers_mart" in names
        assert "products_mart" in names

    def test_empty_query(self, populated_store: IngestionStore) -> None:
        # Empty string matches everything
        results = text_search(populated_store, "")
        assert len(results) == len(populated_store.nodes)

    def test_search_on_empty_store(self) -> None:
        empty = IngestionStore()
        results = text_search(empty, "anything")
        assert results == []

    def test_match_multiple_fields(self) -> None:
        """A node whose name and description both contain the query still appears once."""
        s = IngestionStore()
        s.add_node("n1", "table", "orders", description="orders table")
        results = text_search(s, "orders")
        assert len(results) == 1
