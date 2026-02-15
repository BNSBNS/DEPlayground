"""Event validation rules.

This module contains pure validation functions that operate on domain models.
No external dependencies - pure business logic.
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from src.ingestion.domain.models import EnrichedTradeEvent, RawEvent, SourceMetadata


class ValidationResult:
    """Result of a validation operation."""

    def __init__(self, is_valid: bool, errors: list[str] | None = None):
        self.is_valid = is_valid
        self.errors = errors or []

    def __bool__(self) -> bool:
        return self.is_valid

    @classmethod
    def valid(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def invalid(cls, *errors: str) -> "ValidationResult":
        return cls(is_valid=False, errors=list(errors))


def validate_raw_event(raw_data: dict[str, Any]) -> ValidationResult:
    """Validate raw event data has required fields.

    Args:
        raw_data: Dictionary from external source

    Returns:
        ValidationResult indicating if the data is valid
    """
    errors = []

    # Check for required fields (depends on source, but these are common)
    required_fields = ["symbol", "price"]
    for field in required_fields:
        if field not in raw_data:
            errors.append(f"Missing required field: {field}")

    # Validate price is numeric
    if "price" in raw_data:
        try:
            price = float(raw_data["price"])
            if price < 0:
                errors.append("Price cannot be negative")
        except (TypeError, ValueError):
            errors.append(f"Invalid price value: {raw_data['price']}")

    # Validate volume if present
    if "volume" in raw_data:
        try:
            volume = float(raw_data["volume"])
            if volume <= 0:
                errors.append("Volume must be positive")
        except (TypeError, ValueError):
            errors.append(f"Invalid volume value: {raw_data['volume']}")

    return ValidationResult.valid() if not errors else ValidationResult.invalid(*errors)


def validate_symbol(symbol: str) -> ValidationResult:
    """Validate trading symbol format.

    Args:
        symbol: Trading symbol to validate

    Returns:
        ValidationResult
    """
    if not symbol:
        return ValidationResult.invalid("Symbol cannot be empty")

    if len(symbol) > 20:
        return ValidationResult.invalid("Symbol exceeds maximum length of 20")

    if not symbol.replace("_", "").isalnum():
        return ValidationResult.invalid("Symbol must contain only alphanumeric characters and underscores")

    if not symbol.isupper():
        return ValidationResult.invalid("Symbol must be uppercase")

    return ValidationResult.valid()


def validate_price(price: Decimal | float | str) -> ValidationResult:
    """Validate price value.

    Args:
        price: Price to validate

    Returns:
        ValidationResult
    """
    try:
        decimal_price = Decimal(str(price))
    except Exception:
        return ValidationResult.invalid(f"Invalid price format: {price}")

    if decimal_price < 0:
        return ValidationResult.invalid("Price cannot be negative")

    # Check precision (max 8 decimal places)
    if decimal_price.as_tuple().exponent < -8:
        return ValidationResult.invalid("Price exceeds maximum precision of 8 decimal places")

    return ValidationResult.valid()


def validate_volume(volume: Decimal | float | str) -> ValidationResult:
    """Validate volume value.

    Args:
        volume: Volume to validate

    Returns:
        ValidationResult
    """
    try:
        decimal_volume = Decimal(str(volume))
    except Exception:
        return ValidationResult.invalid(f"Invalid volume format: {volume}")

    if decimal_volume <= 0:
        return ValidationResult.invalid("Volume must be positive")

    return ValidationResult.valid()


def validate_timestamp(
    timestamp: datetime,
    max_future_seconds: int = 60,
    max_past_days: int = 7,
) -> ValidationResult:
    """Validate event timestamp is within acceptable range.

    Args:
        timestamp: Timestamp to validate
        max_future_seconds: Maximum seconds in the future allowed
        max_past_days: Maximum days in the past allowed

    Returns:
        ValidationResult
    """
    now = datetime.now(UTC)

    # Check if too far in the future
    max_future = now + timedelta(seconds=max_future_seconds)
    if timestamp > max_future:
        return ValidationResult.invalid(
            f"Timestamp is too far in the future: {timestamp.isoformat()}"
        )

    # Check if too far in the past
    max_past = now - timedelta(days=max_past_days)
    if timestamp < max_past:
        return ValidationResult.invalid(
            f"Timestamp is too far in the past: {timestamp.isoformat()}"
        )

    return ValidationResult.valid()


def validate_enriched_trade_event(event: EnrichedTradeEvent) -> ValidationResult:
    """Validate a complete enriched trade event.

    Args:
        event: Event to validate

    Returns:
        ValidationResult
    """
    errors = []

    # Validate symbol
    symbol_result = validate_symbol(event.symbol)
    if not symbol_result:
        errors.extend(symbol_result.errors)

    # Validate price
    price_result = validate_price(event.price)
    if not price_result:
        errors.extend(price_result.errors)

    # Validate volume
    volume_result = validate_volume(event.volume)
    if not volume_result:
        errors.extend(volume_result.errors)

    # Validate timestamp
    timestamp_result = validate_timestamp(event.event_timestamp)
    if not timestamp_result:
        errors.extend(timestamp_result.errors)

    return ValidationResult.valid() if not errors else ValidationResult.invalid(*errors)


def is_duplicate(
    event: EnrichedTradeEvent,
    seen_keys: set[str],
) -> bool:
    """Check if event is a duplicate based on idempotency key.

    Args:
        event: Event to check
        seen_keys: Set of already processed idempotency keys

    Returns:
        True if duplicate, False otherwise
    """
    if not event.idempotency_key:
        event.compute_idempotency_key()

    return event.idempotency_key in seen_keys


def try_parse_trade_event(raw_data: dict[str, Any]) -> EnrichedTradeEvent | None:
    """Try to parse raw data into an EnrichedTradeEvent.

    Args:
        raw_data: Raw event data

    Returns:
        EnrichedTradeEvent if parsing succeeds, None otherwise
    """
    try:
        return EnrichedTradeEvent.from_kafka_value(raw_data)
    except (ValidationError, KeyError, ValueError):
        return None
