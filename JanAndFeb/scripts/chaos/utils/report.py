"""Chaos test reporting utilities.

Generates comprehensive reports of chaos test results,
including pass/fail status, DLQ analysis, and recommendations.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    """Test result status."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass
class TestCase:
    """Individual test case result."""

    name: str
    category: str  # streaming, batch
    description: str
    status: TestStatus = TestStatus.SKIPPED
    expected_behavior: str = ""
    actual_behavior: str = ""
    dlq_messages_expected: int = 0
    dlq_messages_actual: int = 0
    duration_ms: float = 0
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == TestStatus.PASSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "status": self.status.value,
            "expected_behavior": self.expected_behavior,
            "actual_behavior": self.actual_behavior,
            "dlq_messages_expected": self.dlq_messages_expected,
            "dlq_messages_actual": self.dlq_messages_actual,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "details": self.details,
        }


@dataclass
class ChaosReport:
    """Comprehensive chaos test report.

    Collects test results and generates reports in multiple formats.

    Example:
        report = ChaosReport("Streaming Chaos Test")

        test = TestCase(
            name="Poison Pill - Invalid JSON",
            category="streaming",
            description="Send malformed JSON to Kafka",
        )
        test.status = TestStatus.PASSED
        test.expected_behavior = "Message routed to DLQ"
        test.actual_behavior = "Message found in trades-dlq topic"

        report.add_test(test)
        report.print_summary()
        report.export_json("chaos_report.json")
    """

    name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    tests: list[TestCase] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_test(self, test: TestCase) -> None:
        """Add a test case to the report."""
        self.tests.append(test)

    def complete(self) -> None:
        """Mark the report as complete."""
        self.completed_at = datetime.now(UTC)

    @property
    def total_tests(self) -> int:
        return len(self.tests)

    @property
    def passed_tests(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.PASSED)

    @property
    def failed_tests(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.FAILED)

    @property
    def error_tests(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.ERROR)

    @property
    def skipped_tests(self) -> int:
        return sum(1 for t in self.tests if t.status == TestStatus.SKIPPED)

    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests * 100

    @property
    def total_duration_ms(self) -> float:
        return sum(t.duration_ms for t in self.tests)

    def get_by_category(self, category: str) -> list[TestCase]:
        """Get tests by category."""
        return [t for t in self.tests if t.category == category]

    def get_failures(self) -> list[TestCase]:
        """Get failed tests."""
        return [t for t in self.tests if t.status == TestStatus.FAILED]

    def get_errors(self) -> list[TestCase]:
        """Get error tests."""
        return [t for t in self.tests if t.status == TestStatus.ERROR]

    def print_summary(self) -> None:
        """Print a human-readable summary."""
        if not self.completed_at:
            self.complete()

        duration = (self.completed_at - self.started_at).total_seconds()

        print("\n" + "=" * 70)
        print(f"CHAOS TEST REPORT: {self.name}")
        print("=" * 70)

        print(f"\nStarted:  {self.started_at.isoformat()}")
        print(f"Finished: {self.completed_at.isoformat()}")
        print(f"Duration: {duration:.2f}s")

        print("\n" + "-" * 70)
        print("SUMMARY")
        print("-" * 70)



        print(f"   Pass Rate: {self.pass_rate:.1f}%")

        # Group by category
        categories = set(t.category for t in self.tests)
        for category in sorted(categories):
            cat_tests = self.get_by_category(category)
            cat_passed = sum(1 for t in cat_tests if t.passed)
            print(f"\n   [{category.upper()}] {cat_passed}/{len(cat_tests)} passed")

        # Print failures
        if self.failed_tests > 0:
            print("\n" + "-" * 70)
            print("FAILURES")
            print("-" * 70)
            for test in self.get_failures():
                print(f"\n❌ {test.name}")
                print(f"   Category: {test.category}")
                print(f"   Expected: {test.expected_behavior}")
                print(f"   Actual:   {test.actual_behavior}")
                if test.error_message:
                    print(f"   Error:    {test.error_message}")

        # Print errors
        if self.error_tests > 0:
            print("\n" + "-" * 70)
            print("ERRORS")
            print("-" * 70)
            for test in self.get_errors():
                print(f"\n⚠️  {test.name}")
                print(f"   Error: {test.error_message}")

        # DLQ Summary
        total_dlq_expected = sum(t.dlq_messages_expected for t in self.tests)
        total_dlq_actual = sum(t.dlq_messages_actual for t in self.tests)
        if total_dlq_expected > 0 or total_dlq_actual > 0:
            print("\n" + "-" * 70)
            print("DLQ SUMMARY")
            print("-" * 70)
            print(f"\n   Expected DLQ messages: {total_dlq_expected}")
            print(f"   Actual DLQ messages:   {total_dlq_actual}")
            if total_dlq_actual > total_dlq_expected:
                print("   ⚠️  More DLQ messages than expected - investigate!")

        print("\n" + "=" * 70)

    def print_detailed(self) -> None:
        """Print detailed test results."""
        self.print_summary()

        print("\nDETAILED RESULTS")
        print("-" * 70)

        for i, test in enumerate(self.tests, 1):
            icon = {
                TestStatus.PASSED: "",
                TestStatus.FAILED: "❌",
                TestStatus.ERROR: "⚠️",
                TestStatus.SKIPPED: "⏭️",
            }.get(test.status, "?")

            print(f"\n{i}. {icon} {test.name}")
            print(f"   Category:    {test.category}")
            print(f"   Description: {test.description}")
            print(f"   Status:      {test.status.value}")
            print(f"   Duration:    {test.duration_ms:.2f}ms")

            if test.expected_behavior:
                print(f"   Expected:    {test.expected_behavior}")
            if test.actual_behavior:
                print(f"   Actual:      {test.actual_behavior}")
            if test.dlq_messages_expected > 0:
                print(f"   DLQ Expected: {test.dlq_messages_expected}")
                print(f"   DLQ Actual:   {test.dlq_messages_actual}")
            if test.error_message:
                print(f"   Error:       {test.error_message}")

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        if not self.completed_at:
            self.complete()

        return {
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (self.completed_at - self.started_at).total_seconds(),
            "summary": {
                "total": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
                "errors": self.error_tests,
                "skipped": self.skipped_tests,
                "pass_rate": self.pass_rate,
            },
            "tests": [t.to_dict() for t in self.tests],
            "metadata": self.metadata,
        }

    def export_json(self, filepath: str) -> None:
        """Export report to JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def export_markdown(self, filepath: str) -> None:
        """Export report to Markdown file."""
        if not self.completed_at:
            self.complete()

        lines = [
            f"# Chaos Test Report: {self.name}",
            "",
            "## Summary",
            "",
            f"- **Started:** {self.started_at.isoformat()}",
            f"- **Completed:** {self.completed_at.isoformat()}",
            f"- **Duration:** {(self.completed_at - self.started_at).total_seconds():.2f}s",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Tests | {self.total_tests} |",
            f"| Passed | {self.passed_tests} |",
            f"| Failed | {self.failed_tests} |",
            f"| Errors | {self.error_tests} |",
            f"| Pass Rate | {self.pass_rate:.1f}% |",
            "",
            "## Test Results",
            "",
        ]

        for category in sorted(set(t.category for t in self.tests)):
            lines.append(f"### {category.title()}")
            lines.append("")
            lines.append("| Test | Status | Duration | DLQ |")
            lines.append("|------|--------|----------|-----|")

            for test in self.get_by_category(category):
                status_icon = {
                    TestStatus.PASSED: "",
                    TestStatus.FAILED: "❌",
                    TestStatus.ERROR: "⚠️",
                    TestStatus.SKIPPED: "⏭️",
                }.get(test.status, "?")

                lines.append(
                    f"| {test.name} | {status_icon} {test.status.value} | "
                    f"{test.duration_ms:.0f}ms | {test.dlq_messages_actual} |"
                )
            lines.append("")

        if self.failed_tests > 0:
            lines.append("## Failures")
            lines.append("")
            for test in self.get_failures():
                lines.append(f"### {test.name}")
                lines.append("")
                lines.append(f"- **Expected:** {test.expected_behavior}")
                lines.append(f"- **Actual:** {test.actual_behavior}")
                if test.error_message:
                    lines.append(f"- **Error:** {test.error_message}")
                lines.append("")

        with open(filepath, "w") as f:
            f.write("\n".join(lines))
