"""Schema scanner — enumerate tables and columns via SQLAlchemy inspection."""

from __future__ import annotations

from src.db.adapter import AbstractDBAdapter
from src.discovery.classification import classify_column
from src.discovery.pii_detector import PIIDetector, get_detector
from src.models import ColumnInfo, TableInfo


def scan_schema(
    adapter: AbstractDBAdapter,
    detector: PIIDetector | None = None,
    sample_values: dict[str, list[str]] | None = None,
) -> list[TableInfo]:
    """Enumerate all tables and classify each column for PII.

    Args:
        adapter: Database adapter to use for introspection.
        detector: PIIDetector instance; uses default if None.
        sample_values: Optional dict of {table.column: [values]} for regex-based detection.

    Returns:
        List of TableInfo objects with PII classifications applied.
    """
    if detector is None:
        detector = get_detector()

    tables: list[TableInfo] = []
    for table_name in adapter.get_table_names():
        cols: list[ColumnInfo] = []
        for col_meta in adapter.get_columns(table_name):
            col_name: str = str(col_meta["name"])
            data_type: str = str(col_meta["type"])
            nullable: bool = bool(col_meta.get("nullable", True))

            # Sample values for this column (if provided)
            key = f"{table_name}.{col_name}"
            samples = sample_values.get(key, []) if sample_values else []

            pii_types = detector.detect(col_name, samples)
            classification, masking = classify_column(col_name, pii_types)

            cols.append(
                ColumnInfo(
                    table_name=table_name,
                    column_name=col_name,
                    data_type=data_type,
                    nullable=nullable,
                    classification=classification,
                    pii_types=pii_types,
                    masking_strategy=masking,
                )
            )

        tables.append(
            TableInfo(
                table_name=table_name,
                columns=cols,
            )
        )

    return tables
