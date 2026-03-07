from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.definitions.parser import parse_feature_definitions
from src.models.features import ValueType


@pytest.fixture
def sample_yaml(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        feature_sets:
          - name: test_features
            entity: customer
            owner: test-team
            tags: [test]
            batch_source: test_table
            stream_source: test-topic
            schedule: hourly
            freshness_sla_minutes: 30
            features:
              - name: feature_a
                value_type: int64
                description: "Count of events"
                aggregation:
                  function: count
                  window: "7 days"

              - name: feature_b
                value_type: float64
                description: "Sum of amounts"
                aggregation:
                  function: sum
                  window: "30 days"
                  filter: "status = 'completed'"

              - name: feature_c
                value_type: string
                description: "Last value"
                aggregation:
                  function: last
                  window: "1 day"
    """)
    yml_path = tmp_path / "test_features.yml"
    yml_path.write_text(content, encoding="utf-8")
    return yml_path


@pytest.fixture
def multi_set_yaml(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        feature_sets:
          - name: set_one
            entity: customer
            batch_source: table_one
            features:
              - name: feat_1
                value_type: int64

          - name: set_two
            entity: product
            batch_source: table_two
            features:
              - name: feat_2
                value_type: float64
              - name: feat_3
                value_type: string
    """)
    yml_path = tmp_path / "multi.yml"
    yml_path.write_text(content, encoding="utf-8")
    return yml_path


class TestParser:
    def test_parse_features(self, sample_yaml: Path) -> None:
        features, sets = parse_feature_definitions(sample_yaml)

        assert len(features) == 3
        assert len(sets) == 1

    def test_feature_set_properties(self, sample_yaml: Path) -> None:
        _, sets = parse_feature_definitions(sample_yaml)
        fs = sets[0]

        assert fs.name == "test_features"
        assert fs.entity == "customer"
        assert fs.batch_source == "test_table"
        assert fs.stream_source == "test-topic"
        assert fs.schedule == "hourly"
        assert len(fs.features) == 3

    def test_feature_properties(self, sample_yaml: Path) -> None:
        features, _ = parse_feature_definitions(sample_yaml)

        f_a = features[0]
        assert f_a.name == "feature_a"
        assert f_a.value_type == ValueType.INT64
        assert f_a.feature_set == "test_features"
        assert f_a.entity == "customer"
        assert f_a.owner == "test-team"
        assert f_a.tags == ["test"]

    def test_aggregation_parsing(self, sample_yaml: Path) -> None:
        features, _ = parse_feature_definitions(sample_yaml)

        f_a = features[0]
        assert f_a.aggregation is not None
        assert f_a.aggregation.function == "count"
        assert f_a.aggregation.window == "7 days"
        assert f_a.aggregation.filter is None

        f_b = features[1]
        assert f_b.aggregation is not None
        assert f_b.aggregation.function == "sum"
        assert f_b.aggregation.filter == "status = 'completed'"

    def test_freshness_sla_inheritance(self, sample_yaml: Path) -> None:
        features, _ = parse_feature_definitions(sample_yaml)

        # All should inherit from feature set default of 30
        for f in features:
            assert f.freshness_sla_minutes == 30

    def test_multi_set_parsing(self, multi_set_yaml: Path) -> None:
        features, sets = parse_feature_definitions(multi_set_yaml)

        assert len(sets) == 2
        assert len(features) == 3

        assert sets[0].name == "set_one"
        assert sets[0].entity == "customer"
        assert sets[1].name == "set_two"
        assert sets[1].entity == "product"

    def test_feature_set_assignment(self, multi_set_yaml: Path) -> None:
        features, _ = parse_feature_definitions(multi_set_yaml)

        assert features[0].feature_set == "set_one"
        assert features[1].feature_set == "set_two"
        assert features[2].feature_set == "set_two"
