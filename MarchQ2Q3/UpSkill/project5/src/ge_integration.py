"""Great Expectations integration: translate contract quality specs into GE expectation suites.

Generates GE-compatible JSON without requiring the GE library to be installed.
The output can be saved and run with the GE CLI:

    great_expectations suite run --suite <name>

Learning note:
    Great Expectations organises assertions about data into "expectation suites" — named
    JSON documents where each entry has an expectation_type and kwargs. This module maps
    the four contract quality rule types to their canonical GE expectation types:

        freshness    → expect_column_max_to_be_between   (timestamp column must be recent)
        volume       → expect_table_row_count_to_be_between
        completeness → expect_column_values_to_not_be_null  (with a "mostly" threshold)
        uniqueness   → expect_column_values_to_be_unique
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models.versions import ContractVersion


def build_expectation_suite(version: ContractVersion) -> dict[str, Any]:
    """Build a GE-compatible expectation suite from a contract version's quality_spec."""
    quality_spec = version.quality_spec or {}
    rules: dict[str, Any] = quality_spec.get("rules", {})
    table = version.schema_spec.get("table", "unknown")

    expectations: list[dict[str, Any]] = []

    if freshness := rules.get("freshness"):
        expectations.extend(_freshness_expectations(freshness))

    if volume := rules.get("volume"):
        expectations.extend(_volume_expectations(volume))

    if completeness := rules.get("completeness"):
        expectations.extend(_completeness_expectations(completeness))

    if uniqueness := rules.get("uniqueness"):
        expectations.extend(_uniqueness_expectations(uniqueness))

    return {
        "expectation_suite_name": f"{table}.quality",
        "expectations": expectations,
        "meta": {
            "contract_id": str(version.contract_id),
            "contract_version": version.version,
            "generated_by": "ge_integration",
        },
    }


def save_expectation_suite(suite: dict[str, Any], output_dir: Path | str = ".") -> Path:
    """Write the suite JSON to disk. Returns the file path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = suite["expectation_suite_name"].replace(".", "_")
    path = output_dir / f"{name}.json"
    path.write_text(json.dumps(suite, indent=2))
    return path


def _freshness_expectations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    col = spec.get("timestamp_column", "updated_at")
    max_staleness_seconds = spec.get("max_staleness_seconds", 3600)
    return [
        {
            "expectation_type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": col},
            "meta": {"rule": "freshness", "description": f"Timestamp column '{col}' must not be null"},
        },
        {
            "expectation_type": "expect_column_max_to_be_between",
            "kwargs": {
                "column": col,
                "min_value": f"now() - interval '{max_staleness_seconds} seconds'",
                "max_value": None,
                "parse_strings_as_datetimes": True,
            },
            "meta": {
                "rule": "freshness",
                "description": f"Latest '{col}' must be within {max_staleness_seconds}s",
            },
        },
    ]


def _volume_expectations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "expectation_type": "expect_table_row_count_to_be_between",
            "kwargs": {
                "min_value": spec.get("min_rows"),
                "max_value": spec.get("max_rows"),
            },
            "meta": {
                "rule": "volume",
                "description": (
                    f"Row count between {spec.get('min_rows')} and {spec.get('max_rows')}"
                ),
            },
        }
    ]


def _completeness_expectations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    max_null_pct = spec.get("max_null_pct", 5.0)
    mostly = 1.0 - (max_null_pct / 100.0)
    return [
        {
            "expectation_type": "expect_column_values_to_not_be_null",
            "kwargs": {"column": col, "mostly": mostly},
            "meta": {
                "rule": "completeness",
                "description": f"Column '{col}' must be non-null >= {mostly * 100:.0f}% of rows",
            },
        }
        for col in spec.get("columns", [])
    ]


def _uniqueness_expectations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "expectation_type": "expect_column_values_to_be_unique",
            "kwargs": {"column": col},
            "meta": {"rule": "uniqueness", "description": f"Column '{col}' must be unique"},
        }
        for col in spec.get("columns", [])
    ]
