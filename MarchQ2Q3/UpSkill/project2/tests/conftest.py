"""Shared test fixtures for GraphRAG unit and integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.ingestion.store import IngestionStore
from src.models.graph import (
    BaseNode,
    ColumnNode,
    DashboardNode,
    DatabaseNode,
    DbtModelNode,
    DocumentChunkNode,
    DocumentNode,
    GraphEdge,
    MetricNode,
    NodeType,
    OwnerNode,
    RelationshipType,
    SchemaNode,
    TableNode,
)
from src.models.retrieval import QueryResponse, RetrievalResult


# --- Graph model fixtures ---


@pytest.fixture
def sample_database_node() -> DatabaseNode:
    return DatabaseNode(id="db-1", name="warehouse")


@pytest.fixture
def sample_schema_node() -> SchemaNode:
    return SchemaNode(id="schema-1", name="staging", database="warehouse")


@pytest.fixture
def sample_table_node() -> TableNode:
    return TableNode(
        id="tbl-1",
        name="orders_mart",
        schema_name="marts",
        database="warehouse",
        row_count=1_000_000,
        description="Order fact table with payment status",
    )


@pytest.fixture
def sample_column_node() -> ColumnNode:
    return ColumnNode(
        id="col-1",
        name="order_id",
        table="orders_mart",
        data_type="uuid",
        nullable=False,
        description="Primary key",
    )


@pytest.fixture
def sample_dbt_model() -> DbtModelNode:
    return DbtModelNode(
        id="dbt-1",
        name="orders_mart",
        materialization="table",
        schema_name="marts",
        description="Order fact table",
        depends_on=["stg_orders", "stg_customers"],
    )


@pytest.fixture
def sample_dashboard() -> DashboardNode:
    return DashboardNode(
        id="dash-1",
        name="executive_kpis",
        tool="tableau",
        url="https://tableau.internal/views/executive-kpis",
        owner="sarah.chen",
    )


@pytest.fixture
def sample_metric() -> MetricNode:
    return MetricNode(
        id="metric-1",
        name="revenue_daily",
        expression="SUM(order_total)",
        table="orders_mart",
    )


@pytest.fixture
def sample_owner() -> OwnerNode:
    return OwnerNode(
        id="owner-1",
        name="sarah.chen",
        team="analytics-team",
        email="sarah.chen@company.com",
        slack_channel="#analytics",
    )


@pytest.fixture
def sample_document() -> DocumentNode:
    return DocumentNode(
        id="doc-1",
        name="data_warehouse_architecture",
        source_path="/docs/data_warehouse_architecture.md",
        content="Our data warehouse follows a medallion architecture.",
    )


@pytest.fixture
def sample_chunk() -> DocumentChunkNode:
    return DocumentChunkNode(
        id="chunk-1",
        name="data_warehouse_architecture_chunk_0",
        document_id="doc-1",
        content="Our data warehouse follows a medallion architecture with three layers.",
        chunk_index=0,
    )


@pytest.fixture
def sample_edge() -> GraphEdge:
    return GraphEdge(
        source_id="tbl-1",
        target_id="schema-1",
        relationship=RelationshipType.belongs_to,
    )


@pytest.fixture
def sample_edges() -> list[GraphEdge]:
    return [
        GraphEdge(
            source_id="tbl-1",
            target_id="schema-1",
            relationship=RelationshipType.belongs_to,
        ),
        GraphEdge(
            source_id="dbt-1",
            target_id="tbl-1",
            relationship=RelationshipType.materializes,
        ),
        GraphEdge(
            source_id="dash-1",
            target_id="metric-1",
            relationship=RelationshipType.displays,
        ),
    ]


# --- Retrieval fixtures ---


@pytest.fixture
def sample_retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        content="The orders_mart table contains order data.",
        source="vector",
        score=0.85,
        metadata={"entity_id": "tbl-1", "source_key": "table:orders_mart"},
    )


@pytest.fixture
def sample_query_response() -> QueryResponse:
    return QueryResponse(
        answer="The orders_mart table is the primary order fact table.",
        confidence=0.82,
        sources=[
            RetrievalResult(
                content="Order fact table with payment status",
                source="vector",
                score=0.9,
            ),
            RetrievalResult(
                content="orders_mart depends on stg_orders and stg_customers",
                source="graph",
                score=0.85,
            ),
        ],
        reasoning_path="Intent: metadata -> Vector search -> Graph expansion",
    )


# --- Store fixture ---


@pytest.fixture
def populated_store() -> IngestionStore:
    """An IngestionStore pre-populated with a small graph."""
    s = IngestionStore()
    s.add_node("db-1", "database", "warehouse")
    s.add_node("schema-1", "schema", "staging", database="warehouse")
    s.add_node(
        "tbl-1", "table", "orders_mart",
        schema_name="marts", database="warehouse",
        description="Order fact table",
    )
    s.add_node(
        "tbl-2", "table", "customers_mart",
        schema_name="marts", database="warehouse",
        description="Customer dimension table",
    )
    s.add_node(
        "tbl-3", "table", "products_mart",
        schema_name="marts", database="warehouse",
        description="Product performance table",
    )
    s.add_edge("tbl-1", "schema-1", "belongs_to")
    s.add_edge("tbl-2", "schema-1", "belongs_to")
    s.add_edge("tbl-1", "tbl-2", "depends_on")
    return s


# --- Mock LLM provider ---


class FakeLLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage: dict[str, int] = {"input_tokens": 10, "output_tokens": 20}
        self.model = "fake-model"
        self.provider = "fake"


class FakeLLMProvider:
    """Deterministic mock LLM for unit tests."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}
        self._default = "This is a mock LLM response."
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> FakeLLMResponse:
        self.calls.append({
            "messages": messages,
            "system": system,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        # Match on first keyword found in the last user message
        last_msg = messages[-1].get("content", "") if messages else ""
        for keyword, response in self._responses.items():
            if keyword.lower() in last_msg.lower():
                return FakeLLMResponse(response)
        return FakeLLMResponse(self._default)


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider(responses={
        "lineage": '{"intent": "lineage"}',
        "owner": '{"intent": "metadata"}',
        "column": '{"intent": "definition"}',
        "default": '{"intent": "general"}',
    })


@pytest.fixture
def mock_pool() -> AsyncMock:
    """Mock asyncpg pool for tests that need DB interaction."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    conn.fetchval.return_value = 1
    conn.fetch.return_value = []
    conn.execute.return_value = None
    return pool
