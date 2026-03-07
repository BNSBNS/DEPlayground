from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.models.features import AggSpec, FeatureDefinition, FeatureSet


def _parse_agg_spec(raw: dict[str, Any] | None) -> AggSpec | None:
    if raw is None:
        return None
    return AggSpec(
        function=raw["function"],
        window=raw["window"],
        filter=raw.get("filter"),
    )


def parse_feature_definitions(path: Path) -> tuple[list[FeatureDefinition], list[FeatureSet]]:
    """Parse a YAML file into FeatureDefinition and FeatureSet objects."""
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    feature_sets: list[FeatureSet] = []
    features: list[FeatureDefinition] = []

    for fs_data in data.get("feature_sets", []):
        fs = FeatureSet(
            name=fs_data["name"],
            entity=fs_data["entity"],
            features=[f["name"] for f in fs_data.get("features", [])],
            batch_source=fs_data.get("batch_source"),
            stream_source=fs_data.get("stream_source"),
            schedule=fs_data.get("schedule", "daily"),
        )
        feature_sets.append(fs)

        for f_data in fs_data.get("features", []):
            fd = FeatureDefinition(
                name=f_data["name"],
                feature_set=fs_data["name"],
                entity=fs_data["entity"],
                value_type=f_data["value_type"],
                description=f_data.get("description", ""),
                owner=f_data.get("owner", fs_data.get("owner", "")),
                tags=f_data.get("tags", fs_data.get("tags", [])),
                batch_source=fs_data.get("batch_source"),
                stream_source=fs_data.get("stream_source"),
                aggregation=_parse_agg_spec(f_data.get("aggregation")),
                transform=f_data.get("transform"),
                freshness_sla_minutes=f_data.get(
                    "freshness_sla_minutes",
                    fs_data.get("freshness_sla_minutes", 60),
                ),
                version=f_data.get("version", 1),
                status=f_data.get("status", "active"),
            )
            features.append(fd)

    return features, feature_sets


def parse_all_definitions(directory: Path) -> tuple[list[FeatureDefinition], list[FeatureSet]]:
    """Parse all YAML files in a directory."""
    all_features: list[FeatureDefinition] = []
    all_sets: list[FeatureSet] = []

    for yml_path in sorted(directory.glob("*.yml")):
        features, sets = parse_feature_definitions(yml_path)
        all_features.extend(features)
        all_sets.extend(sets)

    return all_features, all_sets
