"""Sigma rule loader and model.

Parses Sigma YAML detection rules into structured SigmaRule objects.
Sigma is an open standard for SIEM detection rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SigmaCondition(BaseModel):
    """A single detection condition (field/value matcher)."""

    field: str
    value: str | int | float | bool | list[str]
    modifier: str = "equals"  # equals, contains, startswith, endswith, re, gt, lt, gte, lte


class SigmaDetection(BaseModel):
    """Detection block with named selections and a condition expression."""

    selections: dict[str, list[SigmaCondition]] = Field(default_factory=dict)
    condition: str = "selection"  # e.g. "selection", "selection1 and selection2"


class SigmaRule(BaseModel):
    """A parsed Sigma detection rule."""

    id: str
    title: str
    description: str = ""
    status: str = "experimental"
    level: str = "medium"
    logsource_category: str = ""
    logsource_product: str = ""
    detection: SigmaDetection = Field(default_factory=SigmaDetection)
    tags: list[str] = Field(default_factory=list)
    mitre_technique_ids: list[str] = Field(default_factory=list)

    @property
    def severity(self) -> str:
        """Map Sigma level to severity."""
        mapping = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
        return mapping.get(self.level, "info")


def _parse_detection_block(detection_raw: dict[str, Any]) -> SigmaDetection:
    """Parse the 'detection' block of a Sigma rule."""
    condition = str(detection_raw.get("condition", "selection"))
    selections: dict[str, list[SigmaCondition]] = {}

    for key, value in detection_raw.items():
        if key == "condition":
            continue
        conditions: list[SigmaCondition] = []
        if isinstance(value, dict):
            for field_key, field_val in value.items():
                field_name, modifier = _parse_field_modifier(field_key)
                conditions.append(
                    SigmaCondition(
                        field=field_name,
                        value=field_val,
                        modifier=modifier,
                    )
                )
        elif isinstance(value, list):
            # List of dicts (OR conditions within selection)
            for item in value:
                if isinstance(item, dict):
                    for field_key, field_val in item.items():
                        field_name, modifier = _parse_field_modifier(field_key)
                        conditions.append(
                            SigmaCondition(
                                field=field_name,
                                value=field_val,
                                modifier=modifier,
                            )
                        )
        selections[key] = conditions

    return SigmaDetection(selections=selections, condition=condition)


def _parse_field_modifier(field_key: str) -> tuple[str, str]:
    """Parse Sigma field|modifier syntax. Returns (field_name, modifier)."""
    if "|" in field_key:
        parts = field_key.split("|", 1)
        modifier_map = {
            "contains": "contains",
            "startswith": "startswith",
            "endswith": "endswith",
            "re": "re",
            "gt": "gt",
            "lt": "lt",
            "gte": "gte",
            "lte": "lte",
        }
        return parts[0], modifier_map.get(parts[1], "equals")
    return field_key, "equals"


def _extract_mitre_tags(tags: list[str]) -> list[str]:
    """Extract MITRE technique IDs from Sigma tags (e.g. attack.t1078)."""
    techniques: list[str] = []
    for tag in tags:
        if tag.lower().startswith("attack.t"):
            technique_id = tag.split(".", 1)[1].upper()
            techniques.append(technique_id)
    return techniques


def load_rule(path: Path) -> SigmaRule:
    """Load a single Sigma rule from a YAML file."""
    text = path.read_text(encoding="utf-8")
    return parse_rule_yaml(text, rule_id=path.stem)


def parse_rule_yaml(yaml_text: str, rule_id: str = "unknown") -> SigmaRule:
    """Parse a Sigma rule from YAML text."""
    data: dict[str, Any] = yaml.safe_load(yaml_text) or {}

    tags = data.get("tags", [])
    logsource = data.get("logsource", {})
    detection_raw = data.get("detection", {})

    return SigmaRule(
        id=data.get("id", rule_id),
        title=data.get("title", "Untitled"),
        description=data.get("description", ""),
        status=data.get("status", "experimental"),
        level=data.get("level", "medium"),
        logsource_category=logsource.get("category", ""),
        logsource_product=logsource.get("product", ""),
        detection=_parse_detection_block(detection_raw),
        tags=tags,
        mitre_technique_ids=_extract_mitre_tags(tags),
    )


def load_rules_from_directory(rules_dir: Path) -> list[SigmaRule]:
    """Load all Sigma rules from a directory."""
    rules: list[SigmaRule] = []
    if not rules_dir.exists():
        return rules
    for path in sorted(rules_dir.glob("*.yml")):
        rules.append(load_rule(path))
    return rules
