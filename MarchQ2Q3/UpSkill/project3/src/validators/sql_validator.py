import sqlparse


def validate_sql(sql: str) -> tuple[bool, list[str]]:
    """Validate SQL syntax using sqlparse.

    Returns (is_valid, list_of_errors).
    """
    errors: list[str] = []

    if not sql.strip():
        errors.append("Empty SQL statement")
        return False, errors

    try:
        parsed = sqlparse.parse(sql)
        if not parsed:
            errors.append("Failed to parse SQL")
            return False, errors

        for stmt in parsed:
            if stmt.get_type() is None and str(stmt).strip():
                # sqlparse returns None type for some valid DDL
                tokens = [t for t in stmt.tokens if not t.is_whitespace]
                if not tokens:
                    errors.append("Empty statement found")
    except Exception as exc:
        errors.append(f"SQL parse error: {exc}")
        return False, errors

    return len(errors) == 0, errors
