"""DLQ Inspector for analyzing failed messages.

Provides tools to:
- Read DLQ messages
- Categorize by error type
- Generate reports
- Replay fixed messages
"""

import json
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from confluent_kafka import Consumer, Producer, KafkaError


@dataclass
class DLQEntry:
    """Parsed DLQ message entry."""

    original_message: str
    error_type: str
    error_message: str
    failed_at: datetime
    consumer_group: str
    partition: int
    offset: int
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_kafka_message(cls, msg: dict[str, Any]) -> "DLQEntry":
        """Create DLQEntry from consumed Kafka message."""
        value = msg.get("value", {})
        return cls(
            original_message=value.get("original_message", ""),
            error_type=value.get("error_type", "Unknown"),
            error_message=value.get("error_message", ""),
            failed_at=datetime.fromisoformat(
                value.get("failed_at", datetime.now(UTC).isoformat())
            ),
            consumer_group=value.get("consumer_group", ""),
            partition=value.get("partition", 0),
            offset=value.get("offset", 0),
            raw_data=value,
        )

    def can_be_fixed(self) -> bool:
        """Check if this message might be fixable."""
        # Some error types are potentially fixable
        fixable_errors = ["ValidationError", "KeyError", "TypeError"]
        return self.error_type in fixable_errors

    def get_fix_suggestion(self) -> str:
        """Get a suggestion for fixing this error."""
        suggestions = {
            "JSONDecodeError": "Message is not valid JSON. Check producer serialization.",
            "ValidationError": "Message schema doesn't match. Check required fields and types.",
            "KeyError": "Missing required field. Verify producer is sending all fields.",
            "TypeError": "Wrong data type. Check price/volume are numbers, not strings.",
            "ValueError": "Invalid value. Check enum values (BUY/SELL) and formats.",
            "UnicodeDecodeError": "Encoding issue. Ensure UTF-8 encoding.",
        }
        return suggestions.get(self.error_type, "Unknown error type. Manual investigation required.")


@dataclass
class DLQSummary:
    """Summary of DLQ analysis."""

    total_messages: int = 0
    error_counts: dict[str, int] = field(default_factory=dict)
    fixable_count: int = 0
    time_range: tuple[datetime | None, datetime | None] = (None, None)
    affected_partitions: set[int] = field(default_factory=set)
    consumer_groups: set[str] = field(default_factory=set)


class DLQInspector:
    """Inspector for Dead Letter Queue messages.

    Example:
        inspector = DLQInspector()

        # Get summary
        summary = inspector.get_summary()
        print(f"Total DLQ messages: {summary.total_messages}")

        # Get recent entries
        entries = inspector.get_entries(limit=10)
        for entry in entries:
            print(f"{entry.error_type}: {entry.error_message}")

        # Replay fixed messages
        fixed = [transform(e) for e in entries if e.can_be_fixed()]
        inspector.replay_messages(fixed)
    """

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        dlq_topic: str = "trades-dlq",
        main_topic: str = "trades",
    ):
        """Initialize DLQ inspector.

        Args:
            bootstrap_servers: Kafka broker addresses
            dlq_topic: DLQ topic name
            main_topic: Main topic for replay
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.dlq_topic = dlq_topic
        self.main_topic = main_topic

        self._entries: list[DLQEntry] = []
        self._loaded = False

    def _create_consumer(self) -> Consumer:
        """Create a consumer for the DLQ topic."""
        return Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": f"dlq-inspector-{uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })

    def _create_producer(self) -> Producer:
        """Create a producer for replay."""
        return Producer({
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": "dlq-replay-producer",
            "acks": "all",
        })

    def load_entries(
        self,
        max_entries: int = 1000,
        timeout: float = 10.0,
    ) -> list[DLQEntry]:
        """Load entries from DLQ topic.

        Args:
            max_entries: Maximum entries to load
            timeout: Polling timeout

        Returns:
            List of DLQ entries
        """
        consumer = self._create_consumer()
        entries = []

        try:
            consumer.subscribe([self.dlq_topic])

            import time
            start_time = time.time()

            while len(entries) < max_entries:
                if time.time() - start_time > timeout:
                    break

                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        break
                    continue

                try:
                    value = json.loads(msg.value().decode("utf-8"))
                    entry = DLQEntry.from_kafka_message({"value": value})
                    entries.append(entry)
                except (json.JSONDecodeError, KeyError) as e:
                    # Malformed DLQ message itself
                    entries.append(DLQEntry(
                        original_message=msg.value().decode("utf-8", errors="replace"),
                        error_type="DLQParseError",
                        error_message=str(e),
                        failed_at=datetime.now(UTC),
                        consumer_group="unknown",
                        partition=msg.partition(),
                        offset=msg.offset(),
                    ))

        finally:
            consumer.close()

        self._entries = entries
        self._loaded = True
        return entries

    def get_entries(
        self,
        limit: int | None = None,
        error_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DLQEntry]:
        """Get DLQ entries with optional filtering.

        Args:
            limit: Maximum entries to return
            error_type: Filter by error type
            since: Filter by time

        Returns:
            Filtered list of entries
        """
        if not self._loaded:
            self.load_entries()

        entries = self._entries

        if error_type:
            entries = [e for e in entries if e.error_type == error_type]

        if since:
            entries = [e for e in entries if e.failed_at >= since]

        if limit:
            entries = entries[:limit]

        return entries

    def get_summary(self) -> DLQSummary:
        """Get summary of DLQ state.

        Returns:
            DLQSummary with statistics
        """
        if not self._loaded:
            self.load_entries()

        if not self._entries:
            return DLQSummary()

        error_counts = Counter(e.error_type for e in self._entries)
        fixable_count = sum(1 for e in self._entries if e.can_be_fixed())

        times = [e.failed_at for e in self._entries]
        time_range = (min(times), max(times))

        partitions = {e.partition for e in self._entries}
        groups = {e.consumer_group for e in self._entries}

        return DLQSummary(
            total_messages=len(self._entries),
            error_counts=dict(error_counts),
            fixable_count=fixable_count,
            time_range=time_range,
            affected_partitions=partitions,
            consumer_groups=groups,
        )

    def get_error_breakdown(self) -> dict[str, list[DLQEntry]]:
        """Group entries by error type.

        Returns:
            Dictionary mapping error types to entries
        """
        if not self._loaded:
            self.load_entries()

        breakdown: dict[str, list[DLQEntry]] = {}
        for entry in self._entries:
            if entry.error_type not in breakdown:
                breakdown[entry.error_type] = []
            breakdown[entry.error_type].append(entry)

        return breakdown

    def replay_message(
        self,
        fixed_message: dict[str, Any],
        topic: str | None = None,
    ) -> bool:
        """Replay a fixed message to the main topic.

        Args:
            fixed_message: The corrected message to replay
            topic: Target topic (defaults to main topic)

        Returns:
            True if successful
        """
        topic = topic or self.main_topic
        producer = self._create_producer()

        try:
            value = json.dumps(fixed_message).encode("utf-8")
            key = fixed_message.get("symbol", "").encode("utf-8")

            producer.produce(
                topic=topic,
                value=value,
                key=key,
            )
            producer.flush(timeout=5.0)
            return True
        except Exception:
            return False
        finally:
            producer.flush()

    def replay_messages(
        self,
        fixed_messages: list[dict[str, Any]],
        topic: str | None = None,
    ) -> tuple[int, int]:
        """Replay multiple fixed messages.

        Args:
            fixed_messages: List of corrected messages
            topic: Target topic

        Returns:
            Tuple of (success_count, failure_count)
        """
        success = 0
        failure = 0

        for msg in fixed_messages:
            if self.replay_message(msg, topic):
                success += 1
            else:
                failure += 1

        return success, failure

    def print_report(self) -> None:
        """Print a human-readable DLQ report."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("DLQ INSPECTION REPORT")
        print("=" * 60)

        print(f"\nTotal Messages: {summary.total_messages}")
        print(f"Fixable Messages: {summary.fixable_count}")

        if summary.time_range[0]:
            print(f"Time Range: {summary.time_range[0]} to {summary.time_range[1]}")

        print(f"Affected Partitions: {sorted(summary.affected_partitions)}")
        print(f"Consumer Groups: {summary.consumer_groups}")

        print("\nError Breakdown:")
        print("-" * 40)
        for error_type, count in sorted(
            summary.error_counts.items(), key=lambda x: -x[1]
        ):
            # Get a sample entry for fix suggestion
            sample = next(
                (e for e in self._entries if e.error_type == error_type), None
            )
            suggestion = sample.get_fix_suggestion() if sample else ""
            print(f"  {error_type}: {count}")
            print(f"    → {suggestion}")

        print("\n" + "=" * 60)

    def export_to_json(self, filepath: str) -> None:
        """Export DLQ entries to JSON file.

        Args:
            filepath: Output file path
        """
        if not self._loaded:
            self.load_entries()

        data = {
            "exported_at": datetime.now(UTC).isoformat(),
            "total_entries": len(self._entries),
            "entries": [
                {
                    "original_message": e.original_message,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "failed_at": e.failed_at.isoformat(),
                    "consumer_group": e.consumer_group,
                    "partition": e.partition,
                    "offset": e.offset,
                    "fixable": e.can_be_fixed(),
                    "fix_suggestion": e.get_fix_suggestion(),
                }
                for e in self._entries
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
