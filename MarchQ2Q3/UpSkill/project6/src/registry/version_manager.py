from __future__ import annotations

import structlog

from src.models.features import FeatureDefinition

logger = structlog.get_logger(__name__)

BREAKING_FIELDS = {"value_type", "entity"}
NON_BREAKING_FIELDS = {"description", "tags", "owner", "freshness_sla_minutes", "status"}


class VersionChange:
    def __init__(
        self,
        feature_name: str,
        old_version: int,
        new_version: int,
        is_breaking: bool,
        changed_fields: list[str],
    ) -> None:
        self.feature_name = feature_name
        self.old_version = old_version
        self.new_version = new_version
        self.is_breaking = is_breaking
        self.changed_fields = changed_fields


def compute_version_change(
    old: FeatureDefinition,
    new: FeatureDefinition,
) -> VersionChange | None:
    """Compare two feature definitions and determine version bump."""
    changed: list[str] = []
    is_breaking = False

    old_dict = old.model_dump(exclude={"version"})
    new_dict = new.model_dump(exclude={"version"})

    for field, old_val in old_dict.items():
        new_val = new_dict.get(field)
        if old_val != new_val:
            changed.append(field)
            if field in BREAKING_FIELDS:
                is_breaking = True

    if not changed:
        return None

    if is_breaking:
        new_version = old.version + 1
    else:
        new_version = old.version  # minor: no version bump in simple scheme

    change = VersionChange(
        feature_name=old.name,
        old_version=old.version,
        new_version=new_version,
        is_breaking=is_breaking,
        changed_fields=changed,
    )
    logger.info(
        "version_change_detected",
        feature=old.name,
        breaking=is_breaking,
        fields=changed,
        new_version=new_version,
    )
    return change


def apply_version(definition: FeatureDefinition, change: VersionChange) -> FeatureDefinition:
    """Return a new definition with the updated version."""
    return definition.model_copy(update={"version": change.new_version})
