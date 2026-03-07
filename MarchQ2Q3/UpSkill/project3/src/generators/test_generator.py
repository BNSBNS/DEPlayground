from src.models.fixes import FixType, GeneratedFix, RiskLevel


def generate_dbt_tests(fix: GeneratedFix) -> GeneratedFix | None:
    """Generate dbt schema tests for a given fix."""
    if fix.fix_type not in (FixType.DBT_MODEL_PATCH, FixType.SQL_ALTER):
        return None

    # Extract model name from file path
    model_name = fix.file_path.rsplit("/", maxsplit=1)[-1].replace(".sql", "")

    test_yaml = (
        f"version: 2\n\n"
        f"models:\n"
        f"  - name: {model_name}\n"
        f"    columns:\n"
        f"      - name: id\n"
        f"        tests:\n"
        f"          - not_null\n"
        f"          - unique\n"
        f"    tests:\n"
        f"      - dbt_utils.recency:\n"
        f"          datepart: day\n"
        f"          field: updated_at\n"
        f"          interval: 1\n"
    )

    return GeneratedFix(
        fix_type=FixType.DBT_TEST_ADD,
        file_path=f"models/staging/{model_name}_tests.yml",
        content=test_yaml,
        description=f"Add schema tests for {model_name}",
        risk_level=RiskLevel.LOW,
    )
