"""Streaming issue definitions using Strategy pattern.

Each issue type implements a common interface for generating
problematic messages that test pipeline resilience.

Design Patterns:
- Strategy Pattern: Each issue type is a strategy for generating specific problems
- Factory Pattern: STREAMING_ISSUES registry + create_issue() factory function
- Template Method: Base class defines generate_batch(), subclasses override generate()
"""

import json
import random
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4


@dataclass(frozen=True)
class IssueResult:
    """Immutable result of generating an issue (DTO pattern)."""

    issue_type: str
    message_bytes: bytes
    message_key: bytes | None = None
    expected_error: str = ""
    description: str = ""
    should_dlq: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class IssueGenerator(Protocol):
    """Protocol for issue generators (Interface Segregation)."""

    def generate(self) -> IssueResult: ...
    def generate_batch(self, count: int) -> list[IssueResult]: ...


class StreamingIssue(ABC):
    """Base class for streaming issues (Strategy pattern).

    Each subclass implements a specific type of data issue
    that can occur in streaming pipelines.

    Template Method Pattern:
    - generate_batch() is the template method
    - generate() is the abstract method subclasses must implement
    """

    name: str = "base_issue"
    description: str = "Base streaming issue"
    expected_error: str = "Unknown"
    should_dlq: bool = True

    @abstractmethod
    def generate(self) -> IssueResult:
        """Generate a problematic message (Strategy method).

        Returns:
            IssueResult with the message bytes and metadata
        """
        pass

    def generate_batch(self, count: int = 10) -> list[IssueResult]:
        """Template method - generates multiple issues.

        Args:
            count: Number of issues to generate

        Returns:
            List of IssueResults
        """
        return [self.generate() for _ in range(count)]


class PoisonPillIssue(StreamingIssue):
    """Generate invalid JSON that cannot be parsed.

    Common causes in production:
    - Truncated messages (network issues, producer crash)
    - Binary data sent to JSON topic (misconfigured producer)
    - Encoding corruption (disk errors, memory corruption)

    Expected handling:
    - Consumer catches JSONDecodeError
    - Message routed to DLQ with error context
    - Consumer continues processing next message
    """

    name = "poison_pill"
    description = "Malformed JSON that cannot be parsed"
    expected_error = "JSONDecodeError"

    def __init__(self, variant: str = "random"):
        """Initialize poison pill generator.

        Args:
            variant: Type of poison pill
                - "truncated": Cut off mid-message (simulates network cutoff)
                - "binary": Random binary data (simulates corruption)
                - "partial_json": Missing closing braces (simulates incomplete write)
                - "text": Plain text string (simulates wrong producer)
                - "random": Random variant
        """
        self.variant = variant
        self._variants = ["truncated", "binary", "partial_json", "text"]

    def generate(self) -> IssueResult:
        variant = self.variant
        if variant == "random":
            variant = random.choice(self._variants)

        if variant == "truncated":
            # Valid JSON start, but truncated
            partial = '{"trade_id": "123", "symbol": "AAPL", "pri'
            message = partial.encode("utf-8")
            desc = "Truncated JSON message (simulates network cutoff)"

        elif variant == "binary":
            # Random binary data
            message = bytes(random.randint(0, 255) for _ in range(50))
            desc = "Random binary data (simulates corruption)"

        elif variant == "partial_json":
            # Missing closing braces
            partial = '{"trade_id": "123", "symbol": "AAPL", "price": 150.0'
            message = partial.encode("utf-8")
            desc = "Partial JSON (missing closing braces)"

        else:  # text
            message = "This is not JSON at all!".encode("utf-8")
            desc = "Plain text instead of JSON"

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            expected_error=self.expected_error,
            description=desc,
            should_dlq=True,
            metadata={"variant": variant},
        )


class SchemaViolationIssue(StreamingIssue):
    """Generate JSON with schema violations.

    Common causes in production:
    - Producer schema changes without consumer update
    - Missing required fields (partial updates)
    - Wrong data types (string vs number)
    - Invalid enum values

    Expected handling:
    - Consumer catches ValidationError (pydantic)
    - Message routed to DLQ with validation details
    - Consumer continues processing
    """

    name = "schema_violation"
    description = "Valid JSON with schema errors"
    expected_error = "ValidationError"

    def __init__(self, variant: str = "random"):
        """Initialize schema violation generator.

        Args:
            variant: Type of violation
                - "missing_field": Required field missing
                - "wrong_type": Wrong data type
                - "invalid_enum": Invalid enum value
                - "empty_string": Empty required string
                - "negative_volume": Negative number where positive required
                - "invalid_symbol": Symbol doesn't match pattern
                - "random": Random variant
        """
        self.variant = variant
        self._variants = [
            "missing_field",
            "wrong_type",
            "invalid_enum",
            "empty_string",
            "negative_volume",
            "invalid_symbol",
        ]

    def _base_trade(self) -> dict[str, Any]:
        """Create a valid base trade to modify."""
        return {
            "trade_id": str(uuid4()),
            "symbol": "TEST_SYM",
            "price": "100.50",
            "volume": "10.0",
            "side": "BUY",
            "trader_id": "CHAOS_TEST",
            "event_timestamp": datetime.now(UTC).isoformat(),
        }

    def generate(self) -> IssueResult:
        variant = self.variant
        if variant == "random":
            variant = random.choice(self._variants)

        trade = self._base_trade()

        if variant == "missing_field":
            # Remove a required field
            field = random.choice(["trade_id", "symbol", "price", "volume", "side"])
            del trade[field]
            desc = f"Missing required field: {field}"

        elif variant == "wrong_type":
            # Wrong type for a field
            choice = random.choice(["price_list", "volume_string", "side_number"])
            if choice == "price_list":
                trade["price"] = [100, 200]  # List instead of number
                desc = "Price is a list instead of number"
            elif choice == "volume_string":
                trade["volume"] = "not a number"
                desc = "Volume is non-numeric string"
            else:
                trade["side"] = 123  # Number instead of enum
                desc = "Side is a number instead of string"

        elif variant == "invalid_enum":
            trade["side"] = "HOLD"  # Invalid enum value
            desc = "Invalid enum value: HOLD (should be BUY/SELL)"

        elif variant == "empty_string":
            trade["symbol"] = ""
            desc = "Empty string for required field: symbol"

        elif variant == "negative_volume":
            trade["volume"] = "-10.0"
            desc = "Negative volume (must be positive)"

        else:  # invalid_symbol
            trade["symbol"] = "invalid-symbol!"  # Doesn't match pattern
            desc = "Symbol doesn't match pattern ^[A-Z0-9_]+$"

        message = json.dumps(trade).encode("utf-8")

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            message_key=trade.get("symbol", "UNKNOWN").encode("utf-8"),
            expected_error=self.expected_error,
            description=desc,
            should_dlq=True,
            metadata={"variant": variant, "trade": trade},
        )


class DuplicateEventIssue(StreamingIssue):
    """Generate duplicate events.

    Common causes in production:
    - Producer retries after timeout (at-least-once delivery)
    - Consumer reprocessing after failure
    - Network retransmissions

    Expected handling:
    - NOT routed to DLQ (valid messages)
    - Handled by idempotent writes (INSERT ON CONFLICT)
    - Aggregates should be identical regardless of duplicates

    This tests the idempotency of the pipeline, not error handling.
    """

    name = "duplicate_event"
    description = "Same event sent multiple times"
    expected_error = "None (tests idempotency)"
    should_dlq = False

    def __init__(self, duplicate_count: int = 3):
        """Initialize duplicate generator.

        Args:
            duplicate_count: Number of times to duplicate
        """
        self.duplicate_count = duplicate_count
        self._last_trade_id: str | None = None

    def generate(self) -> IssueResult:
        # Use the same trade_id for all duplicates
        if self._last_trade_id is None:
            self._last_trade_id = str(uuid4())

        trade = {
            "trade_id": self._last_trade_id,
            "symbol": "DUP_TEST",
            "price": "100.50",
            "volume": "10.0",
            "side": "BUY",
            "trader_id": "CHAOS_TEST",
            "event_timestamp": datetime.now(UTC).isoformat(),
        }

        message = json.dumps(trade).encode("utf-8")

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            message_key=b"DUP_TEST",
            expected_error="None",
            description=f"Duplicate event with trade_id: {self._last_trade_id}",
            should_dlq=False,
            metadata={"trade_id": self._last_trade_id},
        )

    def generate_batch(self, count: int = 3) -> list[IssueResult]:
        """Generate a batch of duplicates with same trade_id."""
        self._last_trade_id = str(uuid4())
        return [self.generate() for _ in range(count)]

    def reset(self) -> None:
        """Reset to generate new trade_id on next call."""
        self._last_trade_id = None


class LateEventIssue(StreamingIssue):
    """Generate late-arriving events.

    Common causes in production:
    - Network delays
    - Producer batching with high latency
    - Cross-datacenter replication lag
    - Mobile clients with intermittent connectivity

    Expected handling:
    - NOT routed to DLQ (valid messages)
    - Handled by grace period in windowed aggregation
    - Events within grace period: included in window
    - Events beyond grace period: dropped or logged

    This tests event-time processing and watermarks.
    """

    name = "late_event"
    description = "Event with old timestamp (late arrival)"
    expected_error = "None (tests late event handling)"
    should_dlq = False

    def __init__(self, delay_seconds: int = 120):
        """Initialize late event generator.

        Args:
            delay_seconds: How far in the past the event should be
        """
        self.delay_seconds = delay_seconds

    def generate(self) -> IssueResult:
        # Create event with past timestamp
        event_time = datetime.now(UTC) - timedelta(seconds=self.delay_seconds)

        trade = {
            "trade_id": str(uuid4()),
            "symbol": "LATE_TEST",
            "price": "100.50",
            "volume": "10.0",
            "side": "BUY",
            "trader_id": "CHAOS_TEST",
            "event_timestamp": event_time.isoformat(),
        }

        message = json.dumps(trade).encode("utf-8")

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            message_key=b"LATE_TEST",
            expected_error="None",
            description=f"Event {self.delay_seconds}s late (tests grace period)",
            should_dlq=False,
            metadata={
                "event_time": event_time.isoformat(),
                "delay_seconds": self.delay_seconds,
            },
        )


class OutOfOrderIssue(StreamingIssue):
    """Generate out-of-order events.

    Common causes in production:
    - Multiple partitions with different consumer lag
    - Producer parallelism without ordering guarantees
    - Network routing differences

    Expected handling:
    - NOT routed to DLQ (valid messages)
    - Handled by event-time processing (not processing time)
    - Aggregations use event_timestamp, not arrival order
    """

    name = "out_of_order"
    description = "Events arriving out of chronological order"
    expected_error = "None (tests ordering handling)"
    should_dlq = False

    def __init__(self, symbol: str = "ORDER_TEST"):
        """Initialize out-of-order generator."""
        self.symbol = symbol
        self._sequence: list[datetime] = []

    def generate(self) -> IssueResult:
        # Generate timestamp that's intentionally out of order
        base_time = datetime.now(UTC)

        if not self._sequence:
            # First event: current time
            event_time = base_time
        else:
            # Randomly jump back in time
            jump_back = random.randint(1, 30)
            event_time = base_time - timedelta(seconds=jump_back)

        self._sequence.append(event_time)

        trade = {
            "trade_id": str(uuid4()),
            "symbol": self.symbol,
            "price": str(Decimal(str(random.uniform(90, 110)))),
            "volume": "10.0",
            "side": random.choice(["BUY", "SELL"]),
            "trader_id": "CHAOS_TEST",
            "event_timestamp": event_time.isoformat(),
        }

        message = json.dumps(trade).encode("utf-8")

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            message_key=self.symbol.encode("utf-8"),
            expected_error="None",
            description="Out-of-order event (tests watermark handling)",
            should_dlq=False,
            metadata={"event_time": event_time.isoformat()},
        )


class HighVolumeIssue(StreamingIssue):
    """Generate high volume bursts.

    Tests backpressure handling and consumer scaling.

    Expected handling:
    - NOT routed to DLQ (valid messages)
    - Consumer should handle without OOM
    - May trigger autoscaling
    - Latency may increase but no data loss
    """

    name = "high_volume"
    description = "Burst of events to test backpressure"
    expected_error = "None (tests backpressure)"
    should_dlq = False

    def __init__(self, burst_size: int = 1000):
        """Initialize high volume generator.

        Args:
            burst_size: Number of events in burst
        """
        self.burst_size = burst_size

    def generate(self) -> IssueResult:
        trade = {
            "trade_id": str(uuid4()),
            "symbol": "BURST_TEST",
            "price": str(Decimal(str(random.uniform(90, 110)))),
            "volume": str(Decimal(str(random.uniform(1, 100)))),
            "side": random.choice(["BUY", "SELL"]),
            "trader_id": "CHAOS_TEST",
            "event_timestamp": datetime.now(UTC).isoformat(),
        }

        message = json.dumps(trade).encode("utf-8")

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            message_key=b"BURST_TEST",
            expected_error="None",
            description="High volume burst event",
            should_dlq=False,
        )

    def generate_batch(self, count: int | None = None) -> list[IssueResult]:
        """Generate a burst of events."""
        count = count or self.burst_size
        return [self.generate() for _ in range(count)]


class EncodingIssue(StreamingIssue):
    """Generate encoding issues.

    Common causes in production:
    - Different systems with different default encodings
    - Legacy data with non-UTF8 characters
    - Binary data in string fields
    - Copy-paste from word processors (smart quotes)

    Expected handling:
    - Consumer catches UnicodeDecodeError or JSONDecodeError
    - Message routed to DLQ
    - Consumer continues processing
    """

    name = "encoding_issue"
    description = "Messages with encoding problems"
    expected_error = "UnicodeDecodeError or JSONDecodeError"

    def __init__(self, variant: str = "random"):
        """Initialize encoding issue generator.

        Args:
            variant: Type of encoding issue
                - "latin1": Latin-1 encoded text
                - "invalid_utf8": Invalid UTF-8 sequences
                - "mixed": Valid JSON with non-UTF8 in values
                - "random": Random variant
        """
        self.variant = variant
        self._variants = ["latin1", "invalid_utf8", "mixed"]

    def generate(self) -> IssueResult:
        variant = self.variant
        if variant == "random":
            variant = random.choice(self._variants)

        if variant == "latin1":
            # Latin-1 text that's invalid UTF-8
            text = "Price: 100€ (café special)"
            message = text.encode("latin-1")
            desc = "Latin-1 encoded text (not valid UTF-8)"

        elif variant == "invalid_utf8":
            # Invalid UTF-8 byte sequences
            message = b'{"symbol": "TEST\xff\xfe"}'
            desc = "Invalid UTF-8 byte sequences"

        else:  # mixed
            # Technically valid JSON but with problematic characters
            trade = {
                "trade_id": str(uuid4()),
                "symbol": "TEST_SYM",
                "price": "100.50",
                "volume": "10.0",
                "side": "BUY",
                "trader_id": "Tëst Üsér",  # Non-ASCII
                "event_timestamp": datetime.now(UTC).isoformat(),
            }
            message = json.dumps(trade).encode("utf-8")
            desc = "JSON with non-ASCII characters (may cause issues in strict systems)"

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            expected_error=self.expected_error,
            description=desc,
            should_dlq=True,
            metadata={"variant": variant},
        )


class NullFieldIssue(StreamingIssue):
    """Generate messages with null/None fields.

    Common causes in production:
    - Optional fields serialized as null
    - Database NULL values propagated
    - Partial updates from source systems

    Expected handling:
    - Consumer catches ValidationError
    - Message routed to DLQ
    """

    name = "null_field"
    description = "Messages with null values in fields"
    expected_error = "ValidationError"

    def __init__(self, fields_to_null: list[str] | None = None):
        """Initialize null field generator.

        Args:
            fields_to_null: Fields to set to null (random if not specified)
        """
        self.fields_to_null = fields_to_null or []
        self._nullable_fields = ["price", "volume", "side", "trader_id", "symbol"]

    def generate(self) -> IssueResult:
        trade = {
            "trade_id": str(uuid4()),
            "symbol": "TEST_SYM",
            "price": "100.50",
            "volume": "10.0",
            "side": "BUY",
            "trader_id": "CHAOS_TEST",
            "event_timestamp": datetime.now(UTC).isoformat(),
        }

        # Null out specified fields or random ones
        fields = self.fields_to_null or [random.choice(self._nullable_fields)]
        for field in fields:
            if field in trade:
                trade[field] = None

        message = json.dumps(trade).encode("utf-8")

        return IssueResult(
            issue_type=self.name,
            message_bytes=message,
            expected_error=self.expected_error,
            description=f"Null values in fields: {fields}",
            should_dlq=True,
            metadata={"null_fields": fields},
        )


# =============================================================================
# Factory Pattern: Registry + Factory Function
# =============================================================================

STREAMING_ISSUES: dict[str, type[StreamingIssue]] = {
    "poison_pill": PoisonPillIssue,
    "schema_violation": SchemaViolationIssue,
    "duplicate_event": DuplicateEventIssue,
    "late_event": LateEventIssue,
    "out_of_order": OutOfOrderIssue,
    "high_volume": HighVolumeIssue,
    "encoding_issue": EncodingIssue,
    "null_field": NullFieldIssue,
}


def create_issue(name: str, **kwargs: Any) -> StreamingIssue:
    """Factory function to create issues by name.

    This implements the Factory Pattern, allowing issue creation
    by name without knowing the concrete class.

    Args:
        name: Issue type name
        **kwargs: Issue-specific parameters

    Returns:
        StreamingIssue instance

    Raises:
        ValueError: If issue type not found

    Example:
        issue = create_issue("poison_pill", variant="truncated")
        result = issue.generate()
    """
    if name not in STREAMING_ISSUES:
        raise ValueError(
            f"Unknown issue type: {name}. "
            f"Available: {list(STREAMING_ISSUES.keys())}"
        )
    return STREAMING_ISSUES[name](**kwargs)
