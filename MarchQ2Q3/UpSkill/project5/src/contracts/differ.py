from __future__ import annotations

from typing import Any

from src.models.versions import ContractVersion


def diff_versions(v1: ContractVersion, v2: ContractVersion) -> dict[str, Any]:
    """Produce a human-readable diff between two contract versions."""
    return {
        "from_version": v1.version,
        "to_version": v2.version,
        "schema_changes": _diff_schema(v1.schema_spec, v2.schema_spec),
        "quality_changes": _diff_dict("quality", v1.quality_spec, v2.quality_spec),
        "sla_changes": _diff_dict("sla", v1.sla_spec, v2.sla_spec),
        "consumer_changes": _diff_consumers(v1.consumers, v2.consumers),
        "changelog": v2.changelog,
    }


def _diff_schema(
    old: dict[str, Any], new: dict[str, Any]
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    old_cols = old.get("columns", {})
    new_cols = new.get("columns", {})

    # Removed columns
    for col in sorted(set(old_cols) - set(new_cols)):
        changes.append({
            "change": "column_removed",
            "column": col,
            "breaking": True,
            "old_spec": old_cols[col],
        })

    # Added columns
    for col in sorted(set(new_cols) - set(old_cols)):
        changes.append({
            "change": "column_added",
            "column": col,
            "breaking": False,
            "new_spec": new_cols[col],
        })

    # Modified columns
    for col in sorted(set(old_cols) & set(new_cols)):
        if old_cols[col] != new_cols[col]:
            old_type = old_cols[col].get("type", "")
            new_type = new_cols[col].get("type", "")
            breaking = old_type != new_type
            changes.append({
                "change": "column_modified",
                "column": col,
                "breaking": breaking,
                "old_spec": old_cols[col],
                "new_spec": new_cols[col],
            })

    return changes


def _diff_dict(
    section: str, old: dict[str, Any], new: dict[str, Any]
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []

    all_keys = set(old.keys()) | set(new.keys())
    for key in sorted(all_keys):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes.append({
                "field": f"{section}.{key}",
                "old": str(old_val),
                "new": str(new_val),
            })

    return changes


def _diff_consumers(
    old: list[str], new: list[str]
) -> dict[str, list[str]]:
    old_set = set(old)
    new_set = set(new)
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
    }
