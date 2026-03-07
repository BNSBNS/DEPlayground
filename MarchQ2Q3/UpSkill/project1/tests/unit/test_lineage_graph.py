"""Tests for lineage graph."""

from src.lineage.graph import LineageGraph


class TestLineageGraph:
    def test_add_edge_and_nodes(self) -> None:
        graph = LineageGraph()
        graph.add_edge("a", "b")
        assert graph.has_node("a")
        assert graph.has_node("b")

    def test_get_upstream(self, sample_lineage_graph: LineageGraph) -> None:
        upstream = sample_lineage_graph.get_upstream("fct_orders")
        assert "stg_orders" in upstream
        assert "stg_customers" in upstream
        assert "raw_orders" in upstream
        assert "raw_customers" in upstream

    def test_get_downstream(self, sample_lineage_graph: LineageGraph) -> None:
        downstream = sample_lineage_graph.get_downstream("raw_orders")
        assert "stg_orders" in downstream
        assert "fct_orders" in downstream
        assert "dashboard_revenue" in downstream

    def test_get_upstream_respects_depth(self, sample_lineage_graph: LineageGraph) -> None:
        upstream = sample_lineage_graph.get_upstream("fct_orders", max_depth=1)
        assert "stg_orders" in upstream
        assert "stg_customers" in upstream
        # raw_* are depth 2, should not be included
        assert "raw_orders" not in upstream

    def test_impact_summary(self, sample_lineage_graph: LineageGraph) -> None:
        impact = sample_lineage_graph.get_impact_summary("raw_orders")
        assert impact["total_affected"] == 3  # stg_orders, fct_orders, dashboard_revenue

    def test_to_dict(self) -> None:
        graph = LineageGraph()
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")
        result = graph.to_dict()
        assert set(result["a"]) == {"b", "c"}

    def test_all_nodes(self, sample_lineage_graph: LineageGraph) -> None:
        nodes = sample_lineage_graph.all_nodes()
        assert len(nodes) == 6

    def test_nonexistent_node(self) -> None:
        graph = LineageGraph()
        assert not graph.has_node("missing")
        assert graph.get_upstream("missing") == set()
