from src.models.diagnosis import Diagnosis, DiagnosisCategory
from src.models.events import PipelineFailureEvent
from src.models.fixes import FixType, GeneratedFix, RiskLevel


def generate_dbt_fix(
    event: PipelineFailureEvent,
    diagnosis: Diagnosis,
) -> GeneratedFix | None:
    """Generate dbt model patch based on diagnosis."""
    table = event.affected_table or "unknown_table"
    column = event.affected_column or "unknown_column"

    if diagnosis.category == DiagnosisCategory.SCHEMA_DRIFT:
        # Add a COALESCE wrapper for the missing column
        patch = (
            f"-- Patch: add {column} with safe default\n"
            f"SELECT\n"
            f"    *,\n"
            f"    COALESCE({column}, '') AS {column}_safe\n"
            f"FROM {{{{ ref('stg_{table}') }}}}"
        )
        return GeneratedFix(
            fix_type=FixType.DBT_MODEL_PATCH,
            file_path=f"models/staging/stg_{table}.sql",
            content=patch,
            description=f"Add safe default for {column} in stg_{table}",
            risk_level=RiskLevel.LOW,
        )

    if diagnosis.category == DiagnosisCategory.DATA_QUALITY:
        patch = (
            f"-- Patch: filter nulls in {column}\n"
            f"SELECT *\n"
            f"FROM {{{{ ref('stg_{table}') }}}}\n"
            f"WHERE {column} IS NOT NULL"
        )
        return GeneratedFix(
            fix_type=FixType.DBT_MODEL_PATCH,
            file_path=f"models/staging/stg_{table}.sql",
            content=patch,
            description=f"Filter NULL {column} values in stg_{table}",
            risk_level=RiskLevel.LOW,
        )

    if diagnosis.category == DiagnosisCategory.DEPENDENCY:
        patch = (
            f"-- Patch: fix source reference\n"
            f"SELECT *\n"
            f"FROM {{{{ source('raw', '{table}') }}}}"
        )
        return GeneratedFix(
            fix_type=FixType.DBT_MODEL_PATCH,
            file_path=f"models/staging/stg_{table}.sql",
            content=patch,
            description=f"Fix source reference for {table}",
            risk_level=RiskLevel.LOW,
        )

    return None
