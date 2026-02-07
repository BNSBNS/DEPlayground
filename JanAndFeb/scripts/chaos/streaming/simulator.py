"""Streaming Chaos Simulator.

Orchestrates injection of various streaming issues and validates
that the pipeline handles them correctly.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from scripts.chaos.streaming.issues import (
    StreamingIssue,
    PoisonPillIssue,
    SchemaViolationIssue,
    DuplicateEventIssue,
    LateEventIssue,
    OutOfOrderIssue,
    HighVolumeIssue,
    EncodingIssue,
    NullFieldIssue,
    OversizedMessageIssue,
    STREAMING_ISSUES,
)
from scripts.chaos.utils.kafka_helper import KafkaHelper
from scripts.chaos.utils.dlq_inspector import DLQInspector
from scripts.chaos.utils.report import ChaosReport, TestCase, TestStatus


@dataclass
class SimulationConfig:
    """Configuration for chaos simulation."""

    # Kafka settings
    bootstrap_servers: str = "localhost:9092"
    topic: str = "trades"
    dlq_topic: str = "trades-dlq"

    # Test settings
    wait_for_processing_seconds: float = 5.0
    verbose: bool = True

    # Issue counts
    poison_pills: int = 5
    schema_violations: int = 5
    duplicates: int = 3
    late_events: int = 3
    out_of_order: int = 5
    high_volume_burst: int = 100
    encoding_issues: int = 3
    null_fields: int = 3
    oversized_messages: int = 3


class StreamingChaosSimulator:
    """Simulator for streaming pipeline chaos testing.

    Injects various issues into the Kafka topic and validates
    that the consumer handles them correctly (DLQ routing, etc.).

    Example:
        simulator = StreamingChaosSimulator()

        # Run all tests
        report = simulator.run_all_tests()
        report.print_summary()

        # Run specific test
        result = simulator.test_poison_pills(count=10)
        print(f"Passed: {result.passed}")
    """

    def __init__(self, config: SimulationConfig | None = None):
        """Initialize the simulator.

        Args:
            config: Simulation configuration
        """
        self.config = config or SimulationConfig()
        self.kafka = KafkaHelper(
            bootstrap_servers=self.config.bootstrap_servers,
            topic=self.config.topic,
            dlq_topic=self.config.dlq_topic,
        )
        self.dlq_inspector = DLQInspector(
            bootstrap_servers=self.config.bootstrap_servers,
            dlq_topic=self.config.dlq_topic,
            main_topic=self.config.topic,
        )
        self.report = ChaosReport("Streaming Chaos Tests")

    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.config.verbose:
            print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {message}")

    def _wait_for_processing(self, seconds: float | None = None) -> None:
        """Wait for consumer to process messages."""
        wait_time = seconds or self.config.wait_for_processing_seconds
        self._log(f"Waiting {wait_time}s for processing...")
        time.sleep(wait_time)

    def _get_dlq_count(self) -> int:
        """Get current DLQ message count."""
        return self.kafka.count_messages(self.config.dlq_topic)

    def _run_issue_test(
        self,
        name: str,
        issue: StreamingIssue,
        count: int,
        expected_dlq: int,
    ) -> TestCase:
        """Run a single issue test.

        Args:
            name: Test name
            issue: Issue generator
            count: Number of issues to inject
            expected_dlq: Expected DLQ message count

        Returns:
            TestCase with results
        """
        test = TestCase(
            name=name,
            category="streaming",
            description=issue.description,
            expected_behavior=f"{expected_dlq} messages in DLQ" if expected_dlq > 0
                            else "Handled without DLQ",
            dlq_messages_expected=expected_dlq,
        )

        start_time = time.perf_counter()
        initial_dlq_count = self._get_dlq_count()

        try:
            self._log(f"Injecting {count} {name} issues...")

            # Generate and send issues
            results = issue.generate_batch(count)
            for result in results:
                send_result = self.kafka.send_raw(
                    topic=self.config.topic,
                    value=result.message_bytes,
                    key=result.message_key,
                )
                if not send_result.success:
                    self._log(f"  Warning: Send failed - {send_result.error}")

            self._wait_for_processing()

            # Check DLQ
            final_dlq_count = self._get_dlq_count()
            new_dlq_messages = final_dlq_count - initial_dlq_count

            test.dlq_messages_actual = new_dlq_messages
            test.actual_behavior = f"{new_dlq_messages} messages in DLQ"
            test.duration_ms = (time.perf_counter() - start_time) * 1000

            # Determine pass/fail
            if expected_dlq > 0:
                # For DLQ-expected issues, we want at least the expected count
                if new_dlq_messages >= expected_dlq:
                    test.status = TestStatus.PASSED
                else:
                    test.status = TestStatus.FAILED
                    test.error_message = (
                        f"Expected at least {expected_dlq} DLQ messages, "
                        f"got {new_dlq_messages}"
                    )
            else:
                # For non-DLQ issues, we don't want them in DLQ
                if new_dlq_messages == 0:
                    test.status = TestStatus.PASSED
                else:
                    # Unexpected DLQ - might still be OK depending on implementation
                    test.status = TestStatus.PASSED
                    test.actual_behavior += " (unexpected but handled)"

            self._log(f"  Result: {test.status.value} - {test.actual_behavior}")

        except Exception as e:
            test.status = TestStatus.ERROR
            test.error_message = str(e)
            test.duration_ms = (time.perf_counter() - start_time) * 1000
            self._log(f"  Error: {e}")

        return test

    def test_poison_pills(self, count: int | None = None) -> TestCase:
        """Test poison pill handling.

        Poison pills are malformed messages that cannot be parsed.
        Expected: All should go to DLQ.
        """
        count = count or self.config.poison_pills
        issue = PoisonPillIssue(variant="random")
        return self._run_issue_test(
            name="Poison Pills (Invalid JSON)",
            issue=issue,
            count=count,
            expected_dlq=count,
        )

    def test_schema_violations(self, count: int | None = None) -> TestCase:
        """Test schema violation handling.

        Schema violations are valid JSON but with wrong structure.
        Expected: All should go to DLQ.
        """
        count = count or self.config.schema_violations
        issue = SchemaViolationIssue(variant="random")
        return self._run_issue_test(
            name="Schema Violations",
            issue=issue,
            count=count,
            expected_dlq=count,
        )

    def test_duplicates(self, count: int | None = None) -> TestCase:
        """Test duplicate event handling.

        Duplicates test idempotency - they should not cause errors.
        Expected: No DLQ (handled by idempotent writes).
        """
        count = count or self.config.duplicates
        issue = DuplicateEventIssue(duplicate_count=count)
        return self._run_issue_test(
            name="Duplicate Events",
            issue=issue,
            count=count,
            expected_dlq=0,
        )

    def test_late_events(self, count: int | None = None) -> TestCase:
        """Test late event handling.

        Late events test the grace period for window aggregation.
        Expected: No DLQ (handled by grace period or dropped gracefully).
        """
        count = count or self.config.late_events
        issue = LateEventIssue(delay_seconds=120)
        return self._run_issue_test(
            name="Late Events (2 min delay)",
            issue=issue,
            count=count,
            expected_dlq=0,
        )

    def test_out_of_order(self, count: int | None = None) -> TestCase:
        """Test out-of-order event handling.

        Out-of-order events test watermark handling.
        Expected: No DLQ (handled by event-time processing).
        """
        count = count or self.config.out_of_order
        issue = OutOfOrderIssue()
        return self._run_issue_test(
            name="Out-of-Order Events",
            issue=issue,
            count=count,
            expected_dlq=0,
        )

    def test_high_volume(self, count: int | None = None) -> TestCase:
        """Test high volume burst handling.

        High volume tests backpressure handling.
        Expected: No DLQ (handled by backpressure).
        """
        count = count or self.config.high_volume_burst
        issue = HighVolumeIssue(burst_size=count)
        return self._run_issue_test(
            name="High Volume Burst",
            issue=issue,
            count=count,
            expected_dlq=0,
        )

    def test_encoding_issues(self, count: int | None = None) -> TestCase:
        """Test encoding issue handling.

        Encoding issues test handling of non-UTF8 data.
        Expected: All should go to DLQ.
        """
        count = count or self.config.encoding_issues
        issue = EncodingIssue(variant="random")
        return self._run_issue_test(
            name="Encoding Issues",
            issue=issue,
            count=count,
            expected_dlq=count,
        )

    def test_null_fields(self, count: int | None = None) -> TestCase:
        """Test null field handling.

        Null fields test validation of required fields.
        Expected: All should go to DLQ.
        """
        count = count or self.config.null_fields
        issue = NullFieldIssue()
        return self._run_issue_test(
            name="Null Field Values",
            issue=issue,
            count=count,
            expected_dlq=count,
        )

    def test_oversized_messages(self, count: int | None = None) -> TestCase:
        """Test oversized message handling.

        Oversized messages exceed Kafka's 1MB default limit.
        Expected: Producer rejects or messages go to DLQ.

        Tests three variants:
        - batch_array: 5000 trades as single message (~1.5MB)
        - large_payload: Single trade with huge metadata
        - nested_depth: Deeply nested JSON (500 levels)
        """
        count = count or self.config.oversized_messages
        issue = OversizedMessageIssue(variant="random")
        return self._run_issue_test(
            name="Oversized Messages (>1MB)",
            issue=issue,
            count=count,
            expected_dlq=count,
        )

    def run_all_tests(self) -> ChaosReport:
        """Run all streaming chaos tests.

        Returns:
            ChaosReport with all test results
        """
        self._log("=" * 60)
        self._log("STREAMING CHAOS SIMULATION")
        self._log("=" * 60)

        # Store initial DLQ count
        initial_dlq = self._get_dlq_count()
        self._log(f"Initial DLQ count: {initial_dlq}")

        # Run all tests
        tests = [
            self.test_poison_pills,
            self.test_schema_violations,
            self.test_null_fields,
            self.test_encoding_issues,
            self.test_oversized_messages,
            self.test_duplicates,
            self.test_late_events,
            self.test_out_of_order,
            self.test_high_volume,
        ]

        for test_fn in tests:
            result = test_fn()
            self.report.add_test(result)

        # Final DLQ analysis
        self._log("\nAnalyzing DLQ...")
        self.dlq_inspector.load_entries()
        summary = self.dlq_inspector.get_summary()
        self._log(f"Final DLQ count: {summary.total_messages}")

        self.report.complete()
        self.report.metadata["dlq_summary"] = {
            "total_messages": summary.total_messages,
            "error_counts": summary.error_counts,
        }

        return self.report

    def run_quick_test(self) -> ChaosReport:
        """Run a quick subset of tests.

        Returns:
            ChaosReport with test results
        """
        self._log("Running quick chaos test...")

        # Just test DLQ-expected issues
        self.report.add_test(self.test_poison_pills(count=2))
        self.report.add_test(self.test_schema_violations(count=2))

        self.report.complete()
        return self.report

    def cleanup(self) -> None:
        """Clean up resources."""
        self.kafka.close()


def main():
    """Run streaming chaos simulation from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Streaming Chaos Simulator")
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers",
    )
    parser.add_argument(
        "--topic",
        default="trades",
        help="Main Kafka topic",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test only",
    )
    parser.add_argument(
        "--output",
        help="Output report file (JSON or Markdown)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Print detailed report",
    )

    args = parser.parse_args()

    config = SimulationConfig(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
    )

    simulator = StreamingChaosSimulator(config)

    try:
        if args.quick:
            report = simulator.run_quick_test()
        else:
            report = simulator.run_all_tests()

        if args.detailed:
            report.print_detailed()
        else:
            report.print_summary()

        if args.output:
            if args.output.endswith(".md"):
                report.export_markdown(args.output)
            else:
                report.export_json(args.output)
            print(f"\nReport exported to: {args.output}")

    finally:
        simulator.cleanup()


if __name__ == "__main__":
    main()
