"""Tests for graph and retrieval data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.evaluation import EvalResult, EvalSuite
from src.models.graph import (
    BaseNode,
    ColumnNode,
    DashboardNode,
    DatabaseNode,
    DbtModelNode,
    GraphEdge,
    MetricNode,
    NodeType,
    OwnerNode,
    RelationshipType,
    SchemaNode,
    TableNode,
)
from src.models.retrieval import QueryIntent, QueryResponse, RetrievalResult


class TestNodeCreation:
    def test_database_node(self, sample_database_node: DatabaseNode) -> None:
        assert sample_database_node.node_type == NodeType.database
        assert sample_database_node.name == "warehouse"

    def test_schema_node(self, sample_schema_node: SchemaNode) -> None:
        assert sample_schema_node.node_type == NodeType.schema
        assert sample_schema_node.database == "warehouse"

    def test_table_node(self, sample_table_node: TableNode) -> None:
        assert sample_table_node.node_type == NodeType.table
        assert sample_table_node.row_count == 1_000_000
        assert sample_table_node.schema_name == "marts"

    def test_column_node(self, sample_column_node: ColumnNode) -> None:
        assert sample_column_node.node_type == NodeType.column
        assert sample_column_node.data_type == "uuid"
        assert sample_column_node.nullable is False

    def test_dbt_model_node(self, sample_dbt_model: DbtModelNode) -> None:
        assert sample_dbt_model.node_type == NodeType.dbt_model
        assert sample_dbt_model.materialization == "table"
        assert len(sample_dbt_model.depends_on) == 2

    def test_dashboard_node(self, sample_dashboard: DashboardNode) -> None:
        assert sample_dashboard.node_type == NodeType.dashboard
        assert sample_dashboard.tool == "tableau"

    def test_metric_node(self, sample_metric: MetricNode) -> None:
        assert sample_metric.node_type == NodeType.metric
        assert sample_metric.expression == "SUM(order_total)"

    def test_owner_node(self, sample_owner: OwnerNode) -> None:
        assert sample_owner.node_type == NodeType.owner
        assert sample_owner.team == "analytics-team"

    def test_node_auto_id(self) -> None:
        node = DatabaseNode(name="test_db")
        assert node.id  # UUID was auto-generated
        assert len(node.id) == 36  # UUID format

    def test_node_auto_timestamp(self) -> None:
        node = DatabaseNode(name="test_db")
        assert node.created_at is not None


class TestEdgeCreation:
    def test_basic_edge(self, sample_edge: GraphEdge) -> None:
        assert sample_edge.source_id == "tbl-1"
        assert sample_edge.target_id == "schema-1"
        assert sample_edge.relationship == RelationshipType.belongs_to

    def test_edge_with_properties(self) -> None:
        edge = GraphEdge(
            source_id="a",
            target_id="b",
            relationship=RelationshipType.depends_on,
            properties={"weight": 0.9},
        )
        assert edge.properties["weight"] == 0.9

    def test_all_relationship_types(self) -> None:
        for rel in RelationshipType:
            edge = GraphEdge(source_id="x", target_id="y", relationship=rel)
            assert edge.relationship == rel


class TestRetrievalResult:
    def test_vector_result(self, sample_retrieval_result: RetrievalResult) -> None:
        assert sample_retrieval_result.source == "vector"
        assert sample_retrieval_result.score == 0.85

    def test_graph_result(self) -> None:
        result = RetrievalResult(
            content="orders_mart depends on stg_orders",
            source="graph",
            score=0.9,
            reasoning_path="Cypher: MATCH (n)-[:DEPENDS_ON]->(m)",
        )
        assert result.source == "graph"
        assert result.reasoning_path.startswith("Cypher")

    def test_invalid_source(self) -> None:
        with pytest.raises(ValidationError):
            RetrievalResult(content="test", source="invalid", score=0.5)


class TestQueryResponse:
    def test_valid_response(self, sample_query_response: QueryResponse) -> None:
        assert sample_query_response.confidence == 0.82
        assert len(sample_query_response.sources) == 2

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            QueryResponse(answer="test", confidence=1.0)

        with pytest.raises(ValidationError):
            QueryResponse(answer="test", confidence=-0.1)

    def test_empty_sources(self) -> None:
        resp = QueryResponse(answer="I don't know.", confidence=0.1)
        assert resp.sources == []


class TestEvalResult:
    def test_overall_score(self) -> None:
        result = EvalResult(
            question="test?",
            answer="answer",
            faithfulness=0.8,
            answer_relevancy=0.7,
            context_precision=0.6,
            context_recall=0.9,
        )
        expected = (0.8 + 0.7 + 0.6 + 0.9) / 4
        assert abs(result.overall_score - expected) < 1e-9

    def test_eval_suite_means(self) -> None:
        r1 = EvalResult(
            question="q1", answer="a1",
            faithfulness=0.8, answer_relevancy=0.7,
            context_precision=0.6, context_recall=0.9,
        )
        r2 = EvalResult(
            question="q2", answer="a2",
            faithfulness=0.6, answer_relevancy=0.5,
            context_precision=0.4, context_recall=0.7,
        )
        suite = EvalSuite(results=[r1, r2])
        assert abs(suite.mean_faithfulness - 0.7) < 1e-9
        assert abs(suite.mean_relevancy - 0.6) < 1e-9
        assert abs(suite.mean_precision - 0.5) < 1e-9
        assert abs(suite.mean_recall - 0.8) < 1e-9


class TestQueryIntent:
    def test_all_intents(self) -> None:
        expected = {"lineage", "metadata", "definition", "change", "general"}
        assert {i.value for i in QueryIntent} == expected
