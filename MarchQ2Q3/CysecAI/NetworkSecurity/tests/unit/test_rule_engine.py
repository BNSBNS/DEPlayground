"""Tests for the YAML rule engine."""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from src.detection.rule_engine import RuleEngine
from src.models import AlertSeverity

_RULE_YAML = """
id: test_rule
name: Test Detection Rule
severity: HIGH
mitre: T1046
threshold: 20
window_seconds: 60
protocol: TCP
description: A test rule for unit testing
tags:
  - network
  - test
"""

_MULTI_RULE_YAML = """
- id: rule_one
  name: Rule One
  severity: CRITICAL
  mitre: T1110
  threshold: 10
  window_seconds: 300

- id: rule_two
  name: Rule Two
  severity: MEDIUM
  mitre: T1071
  threshold: 5
  window_seconds: 120
"""


@pytest.fixture()
def rule_dir_single() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d)
        (path / "test_rule.yml").write_text(_RULE_YAML, encoding="utf-8")
        yield path


@pytest.fixture()
def rule_dir_multi() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d)
        (path / "multi.yml").write_text(_MULTI_RULE_YAML, encoding="utf-8")
        yield path


@pytest.fixture()
def real_rules_dir() -> pathlib.Path:
    return pathlib.Path("rules")


class TestRuleEngine:
    def test_loads_single_rule(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        assert len(engine) == 1

    def test_rule_id_accessible(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert rule.id == "test_rule"

    def test_rule_name(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert rule.name == "Test Detection Rule"

    def test_rule_severity(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert rule.severity == AlertSeverity.HIGH

    def test_rule_mitre(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert rule.mitre == "T1046"

    def test_rule_threshold(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert rule.threshold == 20

    def test_rule_window(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert rule.window_seconds == 60

    def test_tags_parsed(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        rule = engine.get("test_rule")
        assert rule is not None
        assert "network" in rule.tags

    def test_loads_multi_rule_file(self, rule_dir_multi: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_multi)
        assert len(engine) == 2

    def test_multi_rule_lookup(self, rule_dir_multi: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_multi)
        r1 = engine.get("rule_one")
        r2 = engine.get("rule_two")
        assert r1 is not None and r1.severity == AlertSeverity.CRITICAL
        assert r2 is not None and r2.severity == AlertSeverity.MEDIUM

    def test_unknown_rule_returns_none(self, rule_dir_single: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_single)
        assert engine.get("does_not_exist") is None

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            engine = RuleEngine(d)
            assert len(engine) == 0

    def test_nonexistent_directory(self) -> None:
        engine = RuleEngine("/nonexistent/path/rules")
        assert len(engine) == 0

    def test_all_rules_returns_list(self, rule_dir_multi: pathlib.Path) -> None:
        engine = RuleEngine(rule_dir_multi)
        rules = engine.all_rules()
        assert len(rules) == 2

    def test_real_rules_dir_loads(self, real_rules_dir: pathlib.Path) -> None:
        if real_rules_dir.exists():
            engine = RuleEngine(real_rules_dir)
            assert len(engine) >= 4

    def test_invalid_severity_defaults_to_medium(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            bad_rule = "id: bad\nname: Bad\nseverity: INVALID\nmitre: T0000\n"
            (pathlib.Path(d) / "bad.yml").write_text(bad_rule, encoding="utf-8")
            engine = RuleEngine(d)
            rule = engine.get("bad")
            assert rule is not None
            assert rule.severity == AlertSeverity.MEDIUM
