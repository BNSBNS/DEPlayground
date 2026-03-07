import re

from src.models.events import ErrorType

PATTERNS: list[tuple[re.Pattern[str], ErrorType]] = [
    (re.compile(r"column.*not found", re.I), ErrorType.SCHEMA_MISMATCH),
    (re.compile(r"undefined column", re.I), ErrorType.SCHEMA_MISMATCH),
    (re.compile(r"relation.*does not exist", re.I), ErrorType.SCHEMA_MISMATCH),
    (re.compile(r"no such column", re.I), ErrorType.SCHEMA_MISMATCH),
    (re.compile(r"schema.*mismatch", re.I), ErrorType.SCHEMA_MISMATCH),
    (re.compile(r"missing column", re.I), ErrorType.SCHEMA_MISMATCH),
    (re.compile(r"null constraint", re.I), ErrorType.NULL_VIOLATION),
    (re.compile(r"not[- ]null", re.I), ErrorType.NULL_VIOLATION),
    (re.compile(r"null value in column", re.I), ErrorType.NULL_VIOLATION),
    (re.compile(r"violates not-null", re.I), ErrorType.NULL_VIOLATION),
    (re.compile(r"type mismatch", re.I), ErrorType.TYPE_MISMATCH),
    (re.compile(r"invalid input syntax", re.I), ErrorType.TYPE_MISMATCH),
    (re.compile(r"cannot cast", re.I), ErrorType.TYPE_MISMATCH),
    (re.compile(r"unexpected row count", re.I), ErrorType.VOLUME_ANOMALY),
    (re.compile(r"row count.*exceeded", re.I), ErrorType.VOLUME_ANOMALY),
    (re.compile(r"volume anomaly", re.I), ErrorType.VOLUME_ANOMALY),
    (re.compile(r"source.*not found", re.I), ErrorType.MISSING_SOURCE),
    (re.compile(r"missing source", re.I), ErrorType.MISSING_SOURCE),
    (re.compile(r"file not found", re.I), ErrorType.MISSING_SOURCE),
    (re.compile(r"permission denied", re.I), ErrorType.PERMISSION_ERROR),
    (re.compile(r"access denied", re.I), ErrorType.PERMISSION_ERROR),
    (re.compile(r"unauthorized", re.I), ErrorType.PERMISSION_ERROR),
    (re.compile(r"timed?\s*out", re.I), ErrorType.TIMEOUT),
    (re.compile(r"deadline exceeded", re.I), ErrorType.TIMEOUT),
    (re.compile(r"connection.*refused", re.I), ErrorType.TIMEOUT),
    (re.compile(r"division by zero", re.I), ErrorType.LOGIC_ERROR),
    (re.compile(r"assertion.*failed", re.I), ErrorType.LOGIC_ERROR),
]


def classify_error(error_message: str) -> ErrorType:
    """Classify an error message into an ErrorType using regex patterns."""
    for pattern, error_type in PATTERNS:
        if pattern.search(error_message):
            return error_type
    return ErrorType.UNKNOWN
