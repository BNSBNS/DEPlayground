"""Rule matching engine.

Matches NormalizedEvents against loaded Sigma rules. Supports field-level
modifiers (equals, contains, startswith, gt, lt, etc.) and boolean conditions
(AND/OR between named selections).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.detection.sigma_loader import SigmaCondition, SigmaRule
    from src.ingestion.normalizer import NormalizedEvent


class RuleMatch:
    """Result of a rule matching against an event."""

    __slots__ = ("event", "matched_fields", "rule")

    def __init__(
        self,
        rule: SigmaRule,
        event: NormalizedEvent,
        matched_fields: dict[str, Any],
    ) -> None:
        self.rule = rule
        self.event = event
        self.matched_fields = matched_fields


def _get_event_field(event: NormalizedEvent, field: str) -> Any:
    """Get a field value from event, checking top-level then details."""
    if hasattr(event, field):
        return getattr(event, field)
    return event.details.get(field)


def _check_equals(expected: str | list[str], event_str: str) -> bool:
    if isinstance(expected, list):
        return event_str in [str(v) for v in expected]
    return event_str == str(expected)


def _check_contains(expected: str | list[str], event_str: str) -> bool:
    if isinstance(expected, list):
        return any(str(v) in event_str for v in expected)
    return str(expected) in event_str


def _check_startswith(expected: str | list[str], event_str: str) -> bool:
    if isinstance(expected, list):
        return any(event_str.startswith(str(v)) for v in expected)
    return event_str.startswith(str(expected))


def _check_endswith(expected: str | list[str], event_str: str) -> bool:
    if isinstance(expected, list):
        return any(event_str.endswith(str(v)) for v in expected)
    return event_str.endswith(str(expected))


_STRING_MATCHERS: dict[str, Any] = {
    "equals": _check_equals,
    "contains": _check_contains,
    "startswith": _check_startswith,
    "endswith": _check_endswith,
}


def _match_string_modifier(modifier: str, expected: str | list[str], event_str: str) -> bool:
    """Match string-based modifiers (equals, contains, startswith, endswith, re)."""
    matcher = _STRING_MATCHERS.get(modifier)
    if matcher is not None:
        result: bool = matcher(expected, event_str)
        return result
    if modifier == "re":
        return bool(re.search(str(expected), event_str))
    return False


def _match_numeric_modifier(modifier: str, expected: Any, event_value: Any) -> bool:
    """Match numeric comparison modifiers (gt, lt, gte, lte)."""
    try:
        num_val = float(str(event_value))
        num_exp = float(str(expected))
    except (ValueError, TypeError):
        return False

    comparisons: dict[str, bool] = {
        "gt": num_val > num_exp,
        "lt": num_val < num_exp,
        "gte": num_val >= num_exp,
        "lte": num_val <= num_exp,
    }
    return comparisons.get(modifier, False)


_NUMERIC_MODIFIERS = {"gt", "lt", "gte", "lte"}


def _match_condition(condition: SigmaCondition, event_value: Any) -> bool:
    """Check if an event value matches a single condition."""
    if event_value is None:
        return False

    if condition.modifier in _NUMERIC_MODIFIERS:
        return _match_numeric_modifier(condition.modifier, condition.value, event_value)

    expected = condition.value if isinstance(condition.value, list) else str(condition.value)
    return _match_string_modifier(condition.modifier, expected, str(event_value))


def _match_selection(
    conditions: list[SigmaCondition],
    event: NormalizedEvent,
) -> tuple[bool, dict[str, Any]]:
    """Match all conditions in a selection (AND logic)."""
    matched_fields: dict[str, Any] = {}
    for cond in conditions:
        event_value = _get_event_field(event, cond.field)
        if _match_condition(cond, event_value):
            matched_fields[cond.field] = event_value
        else:
            return False, {}
    return True, matched_fields


def _evaluate_condition(
    condition_expr: str,
    selection_results: dict[str, bool],
) -> bool:
    """Evaluate Sigma condition expression (e.g. 'selection1 and selection2')."""
    expr = condition_expr.strip()

    if expr in selection_results:
        return selection_results[expr]

    if " and " in expr:
        parts = expr.split(" and ")
        return all(selection_results.get(p.strip(), False) for p in parts)

    if " or " in expr:
        parts = expr.split(" or ")
        return any(selection_results.get(p.strip(), False) for p in parts)

    if expr.startswith("not "):
        inner = expr[4:].strip()
        return not selection_results.get(inner, False)

    return selection_results.get(expr, False)


def match_event(rule: SigmaRule, event: NormalizedEvent) -> RuleMatch | None:
    """Match a single event against a Sigma rule.

    Returns a RuleMatch if the event matches, None otherwise.
    """
    selection_results: dict[str, bool] = {}
    all_matched_fields: dict[str, Any] = {}

    for sel_name, conditions in rule.detection.selections.items():
        matched, fields = _match_selection(conditions, event)
        selection_results[sel_name] = matched
        if matched:
            all_matched_fields.update(fields)

    if _evaluate_condition(rule.detection.condition, selection_results):
        return RuleMatch(rule=rule, event=event, matched_fields=all_matched_fields)
    return None


class RuleEngine:
    """Sigma rule matching engine."""

    def __init__(self, rules: list[SigmaRule] | None = None) -> None:
        self._rules: list[SigmaRule] = list(rules) if rules else []

    @property
    def rules(self) -> list[SigmaRule]:
        """Loaded rules."""
        return list(self._rules)

    def add_rule(self, rule: SigmaRule) -> None:
        """Add a rule to the engine."""
        self._rules.append(rule)

    def match(self, event: NormalizedEvent) -> list[RuleMatch]:
        """Match an event against all loaded rules. Returns all matches."""
        matches: list[RuleMatch] = []
        for rule in self._rules:
            result = match_event(rule, event)
            if result is not None:
                matches.append(result)
        return matches
