from __future__ import annotations

from src.models.entities import ENTITIES
from src.models.features import FeatureDefinition, FeatureSet, ValueType

SUPPORTED_AGG_FUNCTIONS = {"count", "sum", "avg", "min", "max", "last", "first", "count_distinct"}

NUMERIC_TYPES = {ValueType.INT64, ValueType.FLOAT64}
AGG_NUMERIC_ONLY = {"sum", "avg", "min", "max"}


class ValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


def validate_feature_definitions(
    features: list[FeatureDefinition],
    feature_sets: list[FeatureSet],
    known_sources: set[str] | None = None,
) -> list[str]:
    """Validate feature definitions and return list of error messages."""
    errors: list[str] = []
    known_sources = known_sources or set()
    feature_set_names = {fs.name for fs in feature_sets}

    for f in features:
        # Entity exists
        if f.entity not in ENTITIES:
            errors.append(f"Feature '{f.name}': unknown entity '{f.entity}'")

        # Feature set exists
        if f.feature_set not in feature_set_names:
            errors.append(f"Feature '{f.name}': unknown feature_set '{f.feature_set}'")

        # Source validation
        if known_sources:
            if f.batch_source and f.batch_source not in known_sources:
                errors.append(f"Feature '{f.name}': unknown batch_source '{f.batch_source}'")
            if f.stream_source and f.stream_source not in known_sources:
                errors.append(f"Feature '{f.name}': unknown stream_source '{f.stream_source}'")

        # Aggregation validation
        if f.aggregation:
            if f.aggregation.function not in SUPPORTED_AGG_FUNCTIONS:
                errors.append(
                    f"Feature '{f.name}': unsupported aggregation '{f.aggregation.function}'"
                )
            if f.aggregation.function in AGG_NUMERIC_ONLY and f.value_type not in NUMERIC_TYPES:
                errors.append(
                    f"Feature '{f.name}': aggregation '{f.aggregation.function}' "
                    f"requires numeric type, got '{f.value_type.value}'"
                )

    # Validate feature sets
    feature_names = {f.name for f in features}
    for fs in feature_sets:
        if fs.entity not in ENTITIES:
            errors.append(f"FeatureSet '{fs.name}': unknown entity '{fs.entity}'")
        for fname in fs.features:
            if fname not in feature_names:
                errors.append(f"FeatureSet '{fs.name}': unknown feature '{fname}'")

    return errors


def validate_or_raise(
    features: list[FeatureDefinition],
    feature_sets: list[FeatureSet],
    known_sources: set[str] | None = None,
) -> None:
    errors = validate_feature_definitions(features, feature_sets, known_sources)
    if errors:
        raise ValidationError(errors)
