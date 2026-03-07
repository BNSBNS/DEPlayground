from __future__ import annotations

from typing import Any

from src.logging import get_logger
from src.models.versions import ContractVersion

log = get_logger(__name__)


class VersionBump:
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


def compute_next_version(
    previous: ContractVersion, new_spec: dict[str, Any]
) -> tuple[str, str]:
    """Compare new spec against previous version, return (next_semver, bump_type)."""
    bump = _detect_bump(previous, new_spec)
    next_ver = _increment_semver(previous.version, bump)
    log.info(
        "version_computed",
        previous=previous.version,
        next=next_ver,
        bump=bump,
    )
    return next_ver, bump


def _detect_bump(previous: ContractVersion, new_spec: dict[str, Any]) -> str:
    new_schema = new_spec.get("schema", {})
    new_quality = new_spec.get("quality", {})
    new_sla = new_spec.get("sla", {})
    prev_schema = previous.schema_spec
    prev_quality = previous.quality_spec
    prev_sla = previous.sla_spec

    # Check for breaking changes -> MAJOR
    if _has_breaking_schema_changes(prev_schema, new_schema):
        return VersionBump.MAJOR
    if _has_tightened_constraints(prev_quality, new_quality):
        return VersionBump.MAJOR
    if _has_tightened_sla(prev_sla, new_sla):
        return VersionBump.MAJOR

    # Check for non-breaking additions -> MINOR
    if _has_non_breaking_schema_changes(prev_schema, new_schema):
        return VersionBump.MINOR
    if _has_loosened_constraints(prev_quality, new_quality):
        return VersionBump.MINOR

    # Metadata-only -> PATCH
    return VersionBump.PATCH


def _has_breaking_schema_changes(
    prev: dict[str, Any], new: dict[str, Any]
) -> bool:
    prev_cols = prev.get("columns", {})
    new_cols = new.get("columns", {})

    # Column removal is breaking
    for col_name in prev_cols:
        if col_name not in new_cols:
            log.info("breaking_change_detected", reason="column_removed", column=col_name)
            return True

    # Type change is breaking
    for col_name, col_spec in prev_cols.items():
        if col_name in new_cols:
            prev_type = col_spec.get("type", "")
            new_type = new_cols[col_name].get("type", "")
            if prev_type and new_type and prev_type != new_type:
                log.info(
                    "breaking_change_detected",
                    reason="type_changed",
                    column=col_name,
                    prev_type=prev_type,
                    new_type=new_type,
                )
                return True

    return False


def _has_tightened_constraints(
    prev: dict[str, Any], new: dict[str, Any]
) -> bool:
    prev_rules = prev.get("rules", {})
    new_rules = new.get("rules", {})

    # Lower max_null_pct is tighter
    if new_rules.get("max_null_pct", 100) < prev_rules.get("max_null_pct", 100):
        return True

    # Higher min_volume is tighter
    if new_rules.get("min_volume", 0) > prev_rules.get("min_volume", 0):
        return True

    return False


def _has_tightened_sla(prev: dict[str, Any], new: dict[str, Any]) -> bool:
    # Lower max_latency is tighter
    if new.get("max_latency_seconds", float("inf")) < prev.get(
        "max_latency_seconds", float("inf")
    ):
        return True
    # Higher availability is tighter
    if new.get("min_availability_pct", 0) > prev.get("min_availability_pct", 0):
        return True
    return False


def _has_non_breaking_schema_changes(
    prev: dict[str, Any], new: dict[str, Any]
) -> bool:
    prev_cols = set(prev.get("columns", {}).keys())
    new_cols = set(new.get("columns", {}).keys())
    return bool(new_cols - prev_cols)


def _has_loosened_constraints(
    prev: dict[str, Any], new: dict[str, Any]
) -> bool:
    prev_rules = prev.get("rules", {})
    new_rules = new.get("rules", {})

    if new_rules.get("max_null_pct", 100) > prev_rules.get("max_null_pct", 100):
        return True
    if new_rules.get("min_volume", 0) < prev_rules.get("min_volume", 0):
        return True
    return False


def _increment_semver(version: str, bump: str) -> str:
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 1
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0

    if bump == VersionBump.MAJOR:
        return f"{major + 1}.0.0"
    elif bump == VersionBump.MINOR:
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"
