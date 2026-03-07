from src.validators.sql_validator import validate_sql


class TestSqlValidator:
    """Test SQL syntax validation."""

    def test_valid_select(self) -> None:
        valid, errors = validate_sql("SELECT * FROM orders WHERE id = 1;")
        assert valid
        assert errors == []

    def test_valid_alter(self) -> None:
        valid, errors = validate_sql(
            "ALTER TABLE public.orders ADD COLUMN discount TEXT DEFAULT '';"
        )
        assert valid
        assert errors == []

    def test_valid_update(self) -> None:
        valid, errors = validate_sql(
            "UPDATE public.orders SET status = 'active' WHERE status IS NULL;"
        )
        assert valid
        assert errors == []

    def test_empty_sql(self) -> None:
        valid, errors = validate_sql("")
        assert not valid
        assert "Empty SQL statement" in errors

    def test_whitespace_only(self) -> None:
        valid, errors = validate_sql("   \n\t  ")
        assert not valid
        assert "Empty SQL statement" in errors

    def test_multiple_statements(self) -> None:
        sql = "SELECT 1; SELECT 2;"
        valid, errors = validate_sql(sql)
        assert valid
        assert errors == []
