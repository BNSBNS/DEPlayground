import re

from src.models.fixes import GeneratedFix, RiskLevel

FORBIDDEN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDROP\s+TABLE\b", re.I), "DROP TABLE is forbidden"),
    (re.compile(r"\bDROP\s+DATABASE\b", re.I), "DROP DATABASE is forbidden"),
    (re.compile(r"\bTRUNCATE\b", re.I), "TRUNCATE is forbidden"),
    (re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.I | re.S), "DELETE without WHERE is forbidden"),
    (re.compile(r"\bGRANT\b", re.I), "GRANT is forbidden in auto-fixes"),
    (re.compile(r"\bREVOKE\b", re.I), "REVOKE is forbidden in auto-fixes"),
    (re.compile(r"\bALTER\s+ROLE\b", re.I), "ALTER ROLE is forbidden"),
]

PROTECTED_TABLES: set[str] = {
    "users",
    "accounts",
    "payments",
    "audit_log",
    "credentials",
    "secrets",
    "permissions",
}


def check_forbidden_patterns(sql: str) -> list[str]:
    """Check SQL for forbidden patterns. Returns list of violations."""
    violations: list[str] = []
    for pattern, message in FORBIDDEN_PATTERNS:
        if pattern.search(sql):
            violations.append(message)
    return violations


def check_protected_tables(sql: str) -> list[str]:
    """Check if SQL modifies protected tables."""
    violations: list[str] = []
    sql_lower = sql.lower()
    for table in PROTECTED_TABLES:
        if table in sql_lower:
            # Check if it's in a modification context
            modify_patterns = [
                rf"\b(ALTER|UPDATE|DELETE|INSERT\s+INTO|DROP)\b.*\b{table}\b",
                rf"\b{table}\b.*\b(ALTER|UPDATE|DELETE|INSERT\s+INTO|DROP)\b",
            ]
            for mp in modify_patterns:
                if re.search(mp, sql, re.I):
                    violations.append(f"Modification of protected table '{table}' detected")
                    break
    return violations


def classify_risk(fix: GeneratedFix) -> RiskLevel:
    """Classify the risk level of a generated fix."""
    content = fix.content.upper()

    # Critical: DDL on production-like tables
    if any(t in fix.content.lower() for t in PROTECTED_TABLES):
        return RiskLevel.CRITICAL

    # High: ALTER TABLE, any DDL
    if "ALTER TABLE" in content or "CREATE" in content:
        return RiskLevel.HIGH

    # Medium: UPDATE/INSERT
    if "UPDATE" in content or "INSERT" in content:
        return RiskLevel.MEDIUM

    # Low: SELECT-only, comments, tests
    return RiskLevel.LOW


def validate_safety(fix: GeneratedFix) -> tuple[bool, list[str]]:
    """Full safety validation: forbidden patterns + protected tables + risk."""
    errors: list[str] = []

    errors.extend(check_forbidden_patterns(fix.content))
    errors.extend(check_protected_tables(fix.content))

    fix.risk_level = classify_risk(fix)

    return len(errors) == 0, errors
