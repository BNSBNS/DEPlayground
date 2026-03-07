"""Suspicious query pattern detector."""

from __future__ import annotations

import datetime
import re

from src.models import AuditEvent, SuspiciousQueryType

# Keywords that indicate schema introspection
_SCHEMA_KEYWORDS: frozenset[str] = frozenset(
    {
        "information_schema",
        "pg_catalog",
        "sys.tables",
        "sys.columns",
        "show tables",
        "show databases",
        "show columns",
        "describe ",
    }
)

# Tables that likely contain PII (by convention — configurable in production)
_PII_TABLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "user",
        "users",
        "customer",
        "customers",
        "patient",
        "patients",
        "employee",
        "employees",
        "member",
        "members",
        "person",
        "people",
        "contact",
        "profile",
        "profiles",
    }
)


def _is_bulk_select(query: str, row_count: int | None, threshold: int) -> bool:
    """Detect bulk exports: SELECT * or large LIMIT."""
    q = query.strip().upper()
    if not q.startswith("SELECT"):
        return False
    if row_count is not None and row_count > threshold:
        return True
    # Heuristic: no LIMIT clause in query
    if re.search(r"\bSELECT\s+\*", q) and "LIMIT" not in q and "WHERE" not in q:
        return True
    return False


def _is_schema_dump(query: str) -> bool:
    """Detect queries that enumerate schema metadata."""
    lower = query.lower()
    return any(kw in lower for kw in _SCHEMA_KEYWORDS)


def _is_pii_wildcard(query: str) -> bool:
    """Detect SELECT * on tables that likely contain PII."""
    lower = query.lower()
    if not re.search(r"\bselect\s+\*", lower):
        return False
    # Check if any PII table name appears in the FROM clause
    from_match = re.search(r"\bfrom\s+(\S+)", lower)
    if from_match:
        table = from_match.group(1).strip("`\"'[];")
        if any(kw in table for kw in _PII_TABLE_KEYWORDS):
            return True
    return False


def _is_off_hours(timestamp: datetime.datetime, start: int = 22, end: int = 6) -> bool:
    """Return True if the query was executed outside business hours."""
    hour = timestamp.hour
    if start > end:
        # Wraps midnight: e.g., 22:00 to 06:00
        return hour >= start or hour < end
    return start <= hour < end


def analyze_query(
    query: str,
    timestamp: datetime.datetime | None = None,
    row_count: int | None = None,
    bulk_threshold: int = 10_000,
    off_hours_start: int = 22,
    off_hours_end: int = 6,
) -> list[SuspiciousQueryType]:
    """Return a list of suspicious query types matched against the query."""
    reasons: list[SuspiciousQueryType] = []

    if _is_bulk_select(query, row_count, bulk_threshold):
        reasons.append(SuspiciousQueryType.BULK_SELECT)

    if _is_schema_dump(query):
        reasons.append(SuspiciousQueryType.SCHEMA_DUMP)

    if _is_pii_wildcard(query):
        reasons.append(SuspiciousQueryType.PII_TABLE_WILDCARD)

    if timestamp is not None and _is_off_hours(timestamp, off_hours_start, off_hours_end):
        reasons.append(SuspiciousQueryType.OFF_HOURS)

    return reasons


def analyze_event(
    event: AuditEvent,
    bulk_threshold: int = 10_000,
    off_hours_start: int = 22,
    off_hours_end: int = 6,
) -> AuditEvent:
    """Analyse an AuditEvent in-place and set suspicious flags.

    Returns a new AuditEvent with is_suspicious and suspicious_reasons set.
    """
    reasons = analyze_query(
        event.query_text,
        timestamp=event.timestamp,
        row_count=event.row_count,
        bulk_threshold=bulk_threshold,
        off_hours_start=off_hours_start,
        off_hours_end=off_hours_end,
    )
    return event.model_copy(
        update={
            "is_suspicious": len(reasons) > 0,
            "suspicious_reasons": reasons,
        }
    )
