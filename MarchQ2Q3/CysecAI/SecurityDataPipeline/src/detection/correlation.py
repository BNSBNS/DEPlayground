"""Multi-event correlation engine.

Detects attack patterns that span multiple events over time windows:
- "N events of type X within T seconds from same source"
- "event X followed by event Y within T seconds"
- Cross-project alert correlation (e.g., fraud + network alert from same IP)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from src.ingestion.normalizer import NormalizedEvent


class CorrelationRule(BaseModel):
    """Definition of a correlation rule."""

    id: str
    title: str
    description: str = ""
    severity: str = "high"
    mitre_technique_id: str = ""
    window_seconds: int = 600
    rule_type: str  # "threshold", "sequence", "cross_project"

    # Threshold rule: N events matching filter within window
    threshold_count: int = 0
    event_filter: dict[str, str | list[str]] = Field(default_factory=dict)
    group_by: str = "src_ip"  # field to group events by

    # Sequence rule: event_a followed by event_b
    event_a_filter: dict[str, str | list[str]] = Field(default_factory=dict)
    event_b_filter: dict[str, str | list[str]] = Field(default_factory=dict)


class CorrelationMatch(BaseModel):
    """Result of a correlation rule firing."""

    rule_id: str
    rule_title: str
    severity: str
    mitre_technique_id: str
    group_key: str
    event_count: int
    first_event_time: datetime
    last_event_time: datetime
    evidence: dict[str, Any] = Field(default_factory=dict)


def _matches_filter(event: NormalizedEvent, event_filter: dict[str, str | list[str]]) -> bool:
    """Check if an event matches all filter criteria."""
    for field, expected in event_filter.items():
        value = getattr(event, field, None) or event.details.get(field)
        if value is None:
            return False
        if isinstance(expected, list):
            if str(value) not in [str(v) for v in expected]:
                return False
        elif str(value) != str(expected):
            return False
    return True


def _get_group_key(event: NormalizedEvent, group_by: str) -> str:
    """Extract the grouping key from an event."""
    value = getattr(event, group_by, None) or event.details.get(group_by)
    return str(value) if value else "unknown"


class CorrelationEngine:
    """Stateful correlation engine that processes events and detects patterns."""

    def __init__(self, rules: list[CorrelationRule] | None = None) -> None:
        self._rules: list[CorrelationRule] = list(rules) if rules else []
        # Buffer: rule_id -> group_key -> list of (timestamp, event)
        self._buffers: dict[str, dict[str, list[tuple[datetime, NormalizedEvent]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._fired: set[tuple[str, str]] = set()  # (rule_id, group_key) already fired

    @property
    def rules(self) -> list[CorrelationRule]:
        """Active correlation rules."""
        return list(self._rules)

    def add_rule(self, rule: CorrelationRule) -> None:
        """Add a correlation rule."""
        self._rules.append(rule)

    def process_event(self, event: NormalizedEvent) -> list[CorrelationMatch]:
        """Process a single event and return any correlation matches."""
        matches: list[CorrelationMatch] = []
        for rule in self._rules:
            result = self._check_rule(rule, event)
            if result is not None:
                matches.append(result)
        return matches

    def process_events(self, events: list[NormalizedEvent]) -> list[CorrelationMatch]:
        """Process a batch of events. Returns all correlation matches."""
        all_matches: list[CorrelationMatch] = []
        for event in events:
            all_matches.extend(self.process_event(event))
        return all_matches

    def reset(self) -> None:
        """Clear all event buffers and fired state."""
        self._buffers.clear()
        self._fired.clear()

    def _check_rule(self, rule: CorrelationRule, event: NormalizedEvent) -> CorrelationMatch | None:
        """Check if an event triggers a correlation rule."""
        if rule.rule_type == "threshold":
            return self._check_threshold(rule, event)
        if rule.rule_type == "sequence":
            return self._check_sequence(rule, event)
        if rule.rule_type == "cross_project":
            return self._check_threshold(rule, event)  # Same logic, different filters
        return None

    def _check_threshold(
        self, rule: CorrelationRule, event: NormalizedEvent
    ) -> CorrelationMatch | None:
        """Threshold: N events matching filter within window from same group."""
        if not _matches_filter(event, rule.event_filter):
            return None

        group_key = _get_group_key(event, rule.group_by)
        buffer = self._buffers[rule.id][group_key]
        buffer.append((event.timestamp, event))

        # Prune events outside window
        cutoff = event.timestamp - timedelta(seconds=rule.window_seconds)
        buffer[:] = [(ts, e) for ts, e in buffer if ts >= cutoff]

        # Check threshold
        fire_key = (rule.id, group_key)
        if len(buffer) >= rule.threshold_count and fire_key not in self._fired:
            self._fired.add(fire_key)
            return CorrelationMatch(
                rule_id=rule.id,
                rule_title=rule.title,
                severity=rule.severity,
                mitre_technique_id=rule.mitre_technique_id,
                group_key=group_key,
                event_count=len(buffer),
                first_event_time=buffer[0][0],
                last_event_time=buffer[-1][0],
                evidence={
                    "threshold": rule.threshold_count,
                    "actual_count": len(buffer),
                    "window_seconds": rule.window_seconds,
                },
            )
        return None

    def _check_sequence(
        self, rule: CorrelationRule, event: NormalizedEvent
    ) -> CorrelationMatch | None:
        """Sequence: event_a followed by event_b within window."""
        group_key = _get_group_key(event, rule.group_by)
        buffer = self._buffers[rule.id][group_key]

        # Check if this is event_a or event_b
        is_a = _matches_filter(event, rule.event_a_filter)
        is_b = _matches_filter(event, rule.event_b_filter)

        if is_a:
            buffer.append((event.timestamp, event))
            # Prune old entries
            cutoff = event.timestamp - timedelta(seconds=rule.window_seconds)
            buffer[:] = [(ts, e) for ts, e in buffer if ts >= cutoff]
            return None

        if is_b and buffer:
            # Check if there's a matching event_a within window
            cutoff = event.timestamp - timedelta(seconds=rule.window_seconds)
            valid_a = [(ts, e) for ts, e in buffer if ts >= cutoff]
            fire_key = (rule.id, group_key)

            if valid_a and fire_key not in self._fired:
                self._fired.add(fire_key)
                return CorrelationMatch(
                    rule_id=rule.id,
                    rule_title=rule.title,
                    severity=rule.severity,
                    mitre_technique_id=rule.mitre_technique_id,
                    group_key=group_key,
                    event_count=len(valid_a) + 1,
                    first_event_time=valid_a[0][0],
                    last_event_time=event.timestamp,
                    evidence={
                        "event_a_count": len(valid_a),
                        "event_b_type": event.event_type,
                        "window_seconds": rule.window_seconds,
                    },
                )

        return None


# Pre-built correlation rules for common attack patterns
BUILTIN_RULES: list[CorrelationRule] = [
    CorrelationRule(
        id="corr-bf-001",
        title="Brute Force Then Success",
        description="Multiple failed logins followed by success from same IP",
        severity="critical",
        mitre_technique_id="T1110",
        window_seconds=600,
        rule_type="sequence",
        group_by="src_ip",
        event_a_filter={"event_type": "login_failure"},
        event_b_filter={"event_type": "login_success"},
    ),
    CorrelationRule(
        id="corr-lm-001",
        title="Lateral Movement — Multi-Host Access",
        description="Same user authenticates to 3+ hosts within 1 hour",
        severity="high",
        mitre_technique_id="T1021",
        window_seconds=3600,
        rule_type="threshold",
        threshold_count=3,
        group_by="user",
        event_filter={"event_type": "login_success"},
    ),
    CorrelationRule(
        id="corr-xp-001",
        title="Cross-Project Alert Correlation",
        description="Multiple security alerts from same IP within 5 minutes",
        severity="critical",
        mitre_technique_id="T1078",
        window_seconds=300,
        rule_type="cross_project",
        threshold_count=2,
        group_by="src_ip",
        event_filter={"action": "alert"},
    ),
]
