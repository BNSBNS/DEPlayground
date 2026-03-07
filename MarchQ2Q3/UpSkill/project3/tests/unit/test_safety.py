import pytest

from src.models.fixes import FixType, GeneratedFix, RiskLevel
from src.validators.safety import (
    check_forbidden_patterns,
    check_protected_tables,
    classify_risk,
    validate_safety,
)


class TestForbiddenPatterns:
    def test_drop_table_blocked(self) -> None:
        violations = check_forbidden_patterns("DROP TABLE orders;")
        assert any("DROP TABLE" in v for v in violations)

    def test_truncate_blocked(self) -> None:
        violations = check_forbidden_patterns("TRUNCATE orders;")
        assert any("TRUNCATE" in v for v in violations)

    def test_bare_delete_blocked(self) -> None:
        violations = check_forbidden_patterns("DELETE FROM orders;")
        assert any("DELETE" in v for v in violations)

    def test_delete_with_where_allowed(self) -> None:
        violations = check_forbidden_patterns("DELETE FROM orders WHERE id = 1;")
        assert violations == []

    def test_grant_blocked(self) -> None:
        violations = check_forbidden_patterns("GRANT SELECT ON orders TO user1;")
        assert any("GRANT" in v for v in violations)

    def test_safe_alter_allowed(self) -> None:
        violations = check_forbidden_patterns(
            "ALTER TABLE orders ADD COLUMN discount TEXT;"
        )
        assert violations == []

    def test_safe_select_allowed(self) -> None:
        violations = check_forbidden_patterns("SELECT * FROM orders;")
        assert violations == []


class TestProtectedTables:
    def test_modify_users_blocked(self) -> None:
        violations = check_protected_tables("ALTER TABLE users ADD COLUMN foo TEXT;")
        assert any("users" in v for v in violations)

    def test_modify_payments_blocked(self) -> None:
        violations = check_protected_tables("UPDATE payments SET amount = 0;")
        assert any("payments" in v for v in violations)

    def test_select_from_protected_allowed(self) -> None:
        violations = check_protected_tables("SELECT * FROM users;")
        assert violations == []


class TestClassifyRisk:
    def test_alter_table_high(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            content="ALTER TABLE orders ADD COLUMN foo TEXT;",
            description="test",
        )
        assert classify_risk(fix) == RiskLevel.HIGH

    def test_update_medium(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.SQL_UPDATE,
            content="UPDATE orders SET status = 'active';",
            description="test",
        )
        assert classify_risk(fix) == RiskLevel.MEDIUM

    def test_select_low(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.DBT_MODEL_PATCH,
            content="SELECT * FROM {{ ref('stg_orders') }}",
            description="test",
        )
        assert classify_risk(fix) == RiskLevel.LOW

    def test_protected_table_critical(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            content="ALTER TABLE users ADD COLUMN foo TEXT;",
            description="test",
        )
        assert classify_risk(fix) == RiskLevel.CRITICAL


class TestValidateSafety:
    def test_safe_fix_passes(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            content="ALTER TABLE orders ADD COLUMN discount TEXT DEFAULT '';",
            description="Add discount column",
        )
        safe, errors = validate_safety(fix)
        assert safe
        assert errors == []

    def test_dangerous_fix_fails(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            content="DROP TABLE orders;",
            description="Drop orders",
        )
        safe, errors = validate_safety(fix)
        assert not safe
        assert len(errors) > 0
