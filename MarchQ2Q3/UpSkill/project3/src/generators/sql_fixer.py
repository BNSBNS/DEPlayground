from src.models.diagnosis import Diagnosis, DiagnosisCategory
from src.models.events import PipelineFailureEvent
from src.models.fixes import FixType, GeneratedFix, RiskLevel


def generate_sql_fix(
    event: PipelineFailureEvent,
    diagnosis: Diagnosis,
) -> GeneratedFix | None:
    """Generate template-based SQL fix based on diagnosis category."""
    table = event.affected_table or "unknown_table"
    column = event.affected_column or "unknown_column"
    schema = event.schema_name

    if diagnosis.category == DiagnosisCategory.SCHEMA_DRIFT:
        sql = (
            f"ALTER TABLE {schema}.{table}\n"
            f"ADD COLUMN IF NOT EXISTS {column} TEXT DEFAULT '';"
        )
        return GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            file_path=f"migrations/add_{column}_to_{table}.sql",
            content=sql,
            description=f"Add missing column '{column}' to {schema}.{table}",
            risk_level=RiskLevel.MEDIUM,
        )

    if diagnosis.category == DiagnosisCategory.DATA_QUALITY:
        sql = (
            f"UPDATE {schema}.{table}\n"
            f"SET {column} = ''\n"
            f"WHERE {column} IS NULL;"
        )
        return GeneratedFix(
            fix_type=FixType.SQL_UPDATE,
            file_path=f"migrations/fix_nulls_{table}_{column}.sql",
            content=sql,
            description=f"Set default for NULL values in {schema}.{table}.{column}",
            risk_level=RiskLevel.LOW,
        )

    return None
