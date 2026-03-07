"""Tests for Sigma rule loading, parsing, and matching (Phase 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from src.detection.rule_engine import RuleEngine, match_event
from src.detection.sigma_loader import (
    load_rules_from_directory,
    parse_rule_yaml,
)
from src.ingestion.normalizer import NormalizedEvent

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


def _make_event(**kwargs: object) -> NormalizedEvent:
    """Create a NormalizedEvent with defaults."""
    defaults: dict[str, object] = {
        "timestamp": datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
        "source": "test",
        "event_type": "test_event",
    }
    defaults.update(kwargs)
    return NormalizedEvent(**defaults)  # type: ignore[arg-type]


class TestSigmaLoader:
    """Sigma YAML parsing tests."""

    def test_parse_basic_rule(self) -> None:
        yaml_text = """
title: Test Rule
id: test-001
level: high
logsource:
    category: authentication
detection:
    selection:
        event_type: login_failure
    condition: selection
tags:
    - attack.t1110
"""
        rule = parse_rule_yaml(yaml_text)
        assert rule.title == "Test Rule"
        assert rule.id == "test-001"
        assert rule.level == "high"
        assert rule.severity == "high"
        assert rule.logsource_category == "authentication"

    def test_parse_mitre_tags(self) -> None:
        yaml_text = """
title: Multi MITRE
id: test-002
detection:
    selection:
        event_type: test
    condition: selection
tags:
    - attack.credential_access
    - attack.t1110
    - attack.t1078
"""
        rule = parse_rule_yaml(yaml_text)
        assert "T1110" in rule.mitre_technique_ids
        assert "T1078" in rule.mitre_technique_ids

    def test_parse_field_modifiers(self) -> None:
        yaml_text = """
title: Modifier Test
id: test-003
detection:
    selection:
        endpoint|contains: /admin/
    condition: selection
"""
        rule = parse_rule_yaml(yaml_text)
        conditions = rule.detection.selections["selection"]
        assert conditions[0].field == "endpoint"
        assert conditions[0].modifier == "contains"

    def test_parse_list_values(self) -> None:
        yaml_text = """
title: List Values
id: test-004
detection:
    selection:
        query|endswith:
            - ".evil.com"
            - ".darknet.io"
    condition: selection
"""
        rule = parse_rule_yaml(yaml_text)
        conditions = rule.detection.selections["selection"]
        assert isinstance(conditions[0].value, list)
        assert len(conditions[0].value) == 2

    def test_load_rules_from_directory(self) -> None:
        rules = load_rules_from_directory(RULES_DIR)
        assert len(rules) == 5
        titles = {r.title for r in rules}
        assert "Brute Force Login Attempt" in titles
        assert "Large Outbound Data Transfer" in titles

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        rules = load_rules_from_directory(tmp_path)
        assert rules == []

    def test_load_nonexistent_directory(self) -> None:
        rules = load_rules_from_directory(Path("/nonexistent"))
        assert rules == []

    def test_severity_mapping(self) -> None:
        for level, expected in [
            ("critical", "critical"),
            ("high", "high"),
            ("medium", "medium"),
            ("low", "low"),
            ("informational", "info"),
        ]:
            yaml_str = (
                f"title: T\nid: t\nlevel: {level}\n"
                "detection:\n  selection:\n    event_type: x\n  condition: selection"
            )
            rule = parse_rule_yaml(yaml_str)
            assert rule.severity == expected


class TestRuleMatching:
    """Rule engine matching tests."""

    def test_matches_simple_equals(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        event_type: login_failure
    condition: selection
""")
        event = _make_event(event_type="login_failure")
        result = match_event(rule, event)
        assert result is not None
        assert result.rule.id == "t1"

    def test_no_match_on_different_value(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        event_type: login_failure
    condition: selection
""")
        event = _make_event(event_type="login_success")
        assert match_event(rule, event) is None

    def test_matches_contains_modifier(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        endpoint|contains: /admin/
    condition: selection
""")
        event = _make_event(details={"endpoint": "/admin/users"})
        assert match_event(rule, event) is not None

    def test_matches_endswith_list(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        query|endswith:
            - ".evil.com"
            - ".darknet.io"
    condition: selection
""")
        event = _make_event(details={"query": "c2-server.evil.com"})
        assert match_event(rule, event) is not None

    def test_no_match_endswith_list(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        query|endswith:
            - ".evil.com"
    condition: selection
""")
        event = _make_event(details={"query": "google.com"})
        assert match_event(rule, event) is None

    def test_matches_gt_modifier(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        bytes_sent|gt: 100000
    condition: selection
""")
        event = _make_event(details={"bytes_sent": 500000})
        assert match_event(rule, event) is not None

    def test_no_match_gt_below_threshold(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        bytes_sent|gt: 100000
    condition: selection
""")
        event = _make_event(details={"bytes_sent": 5000})
        assert match_event(rule, event) is None

    def test_and_condition(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection1:
        event_type: http_request
    selection2:
        endpoint|contains: /admin/
    condition: selection1 and selection2
""")
        event = _make_event(event_type="http_request", details={"endpoint": "/admin/config"})
        assert match_event(rule, event) is not None

    def test_and_condition_partial_miss(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection1:
        event_type: http_request
    selection2:
        endpoint|contains: /admin/
    condition: selection1 and selection2
""")
        event = _make_event(event_type="http_request", details={"endpoint": "/api/users"})
        assert match_event(rule, event) is None

    def test_or_condition(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection1:
        event_type: login_failure
    selection2:
        event_type: login_success
    condition: selection1 or selection2
""")
        event = _make_event(event_type="login_success")
        assert match_event(rule, event) is not None

    def test_missing_field_no_match(self) -> None:
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        nonexistent_field: value
    condition: selection
""")
        event = _make_event()
        assert match_event(rule, event) is None


class TestRuleEngine:
    """RuleEngine class tests."""

    def test_add_and_match(self) -> None:
        engine = RuleEngine()
        rule = parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        event_type: login_failure
    condition: selection
""")
        engine.add_rule(rule)
        assert len(engine.rules) == 1

        event = _make_event(event_type="login_failure")
        matches = engine.match(event)
        assert len(matches) == 1

    def test_multiple_rules_match(self) -> None:
        engine = RuleEngine()
        for i in range(3):
            engine.add_rule(
                parse_rule_yaml(f"""
title: Rule {i}
id: r{i}
detection:
    selection:
        event_type: login_failure
    condition: selection
""")
            )
        event = _make_event(event_type="login_failure")
        matches = engine.match(event)
        assert len(matches) == 3

    def test_no_matches(self) -> None:
        engine = RuleEngine()
        engine.add_rule(
            parse_rule_yaml("""
title: Test
id: t1
detection:
    selection:
        event_type: login_failure
    condition: selection
""")
        )
        event = _make_event(event_type="dns_query")
        assert engine.match(event) == []

    def test_loads_real_rules(self) -> None:
        rules = load_rules_from_directory(RULES_DIR)
        engine = RuleEngine(rules)
        assert len(engine.rules) == 5

    def test_brute_force_rule_matches(self) -> None:
        rules = load_rules_from_directory(RULES_DIR)
        engine = RuleEngine(rules)
        event = _make_event(event_type="login_failure", action="deny")
        matches = engine.match(event)
        rule_ids = {m.rule.id for m in matches}
        assert "sigma-bf-001" in rule_ids

    def test_exfiltration_rule_matches(self) -> None:
        rules = load_rules_from_directory(RULES_DIR)
        engine = RuleEngine(rules)
        event = _make_event(
            event_type="connection_allowed",
            action="allow",
            details={"bytes_sent": 500000},
        )
        matches = engine.match(event)
        rule_ids = {m.rule.id for m in matches}
        assert "sigma-de-001" in rule_ids

    def test_dns_rule_matches_malicious(self) -> None:
        rules = load_rules_from_directory(RULES_DIR)
        engine = RuleEngine(rules)
        event = _make_event(
            event_type="dns_query",
            details={"query": "c2-server.evil.com"},
        )
        matches = engine.match(event)
        rule_ids = {m.rule.id for m in matches}
        assert "sigma-dns-001" in rule_ids
