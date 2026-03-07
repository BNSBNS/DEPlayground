import pytest

from src.analysis.classifier import classify_error
from src.models.events import ErrorType


class TestClassifyError:
    """Test error classification using regex patterns."""

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("column 'foo' not found in source", ErrorType.SCHEMA_MISMATCH),
            ("undefined column bar", ErrorType.SCHEMA_MISMATCH),
            ("relation 'public.orders' does not exist", ErrorType.SCHEMA_MISMATCH),
            ("missing column 'tax_rate' in upstream", ErrorType.SCHEMA_MISMATCH),
            ("schema mismatch detected", ErrorType.SCHEMA_MISMATCH),
        ],
    )
    def test_schema_patterns(self, message: str, expected: ErrorType) -> None:
        assert classify_error(message) == expected

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("null value in column 'id' violates not-null constraint", ErrorType.NULL_VIOLATION),
            ("NOT NULL constraint failed: orders.customer_id", ErrorType.NULL_VIOLATION),
            ("violates not-null constraint", ErrorType.NULL_VIOLATION),
        ],
    )
    def test_null_patterns(self, message: str, expected: ErrorType) -> None:
        assert classify_error(message) == expected

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("invalid input syntax for type integer", ErrorType.TYPE_MISMATCH),
            ("cannot cast value to numeric", ErrorType.TYPE_MISMATCH),
            ("type mismatch in column 'amount'", ErrorType.TYPE_MISMATCH),
        ],
    )
    def test_type_patterns(self, message: str, expected: ErrorType) -> None:
        assert classify_error(message) == expected

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("connection timed out", ErrorType.TIMEOUT),
            ("deadline exceeded", ErrorType.TIMEOUT),
            ("permission denied for table users", ErrorType.PERMISSION_ERROR),
            ("access denied to resource", ErrorType.PERMISSION_ERROR),
        ],
    )
    def test_infra_patterns(self, message: str, expected: ErrorType) -> None:
        assert classify_error(message) == expected

    def test_unknown_fallback(self) -> None:
        assert classify_error("something completely unexpected happened") == ErrorType.UNKNOWN

    def test_empty_message(self) -> None:
        assert classify_error("") == ErrorType.UNKNOWN
