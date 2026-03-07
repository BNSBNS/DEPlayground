"""YAML-based detection rule loader and registry."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

from src.models import AlertSeverity


@dataclass
class DetectionRule:
    """Configuration for a detection rule loaded from YAML."""

    id: str
    name: str
    severity: AlertSeverity
    mitre: str
    threshold: int = 1
    window_seconds: int = 60
    protocol: str | None = None
    description: str = ""
    tags: list[str] = field(default_factory=list)


def _parse_severity(value: str) -> AlertSeverity:
    try:
        return AlertSeverity(value.upper())
    except ValueError:
        return AlertSeverity.MEDIUM


def _parse_rule(data: dict[str, Any]) -> DetectionRule:
    return DetectionRule(
        id=str(data["id"]),
        name=str(data["name"]),
        severity=_parse_severity(str(data.get("severity", "MEDIUM"))),
        mitre=str(data.get("mitre", "")),
        threshold=int(data.get("threshold", 1)),
        window_seconds=int(data.get("window_seconds", 60)),
        protocol=str(data["protocol"]) if data.get("protocol") else None,
        description=str(data.get("description", "")),
        tags=list(data.get("tags", [])),
    )


class RuleEngine:
    """Loads and provides access to YAML detection rules."""

    def __init__(self, rules_dir: str | pathlib.Path) -> None:
        self._rules: dict[str, DetectionRule] = {}
        self._load_all(pathlib.Path(rules_dir))

    def _load_all(self, directory: pathlib.Path) -> None:
        if not directory.exists():
            return
        for yaml_file in sorted(directory.glob("*.yml")):
            self._load_file(yaml_file)

    def _load_file(self, path: pathlib.Path) -> None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for item in raw:
                rule = _parse_rule(item)
                self._rules[rule.id] = rule
        elif isinstance(raw, dict):
            rule = _parse_rule(raw)
            self._rules[rule.id] = rule

    def get(self, rule_id: str) -> DetectionRule | None:
        return self._rules.get(rule_id)

    def all_rules(self) -> list[DetectionRule]:
        return list(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)
