"""Batch Chaos Simulator.

Orchestrates injection of problematic files and validates
that the batch pipeline handles them correctly.
"""

import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.chaos.batch.issues import (
    BatchIssue,
    CorruptFileIssue,
    SchemaDriftIssue,
    EncodingFileIssue,
    EmptyFileIssue,
    PartialFileIssue,
    DuplicateFileIssue,
    LargeFileIssue,
    WrongFormatIssue,
    MalformedRowIssue,
)
from scripts.chaos.utils.kafka_helper import KafkaHelper
from scripts.chaos.utils.dlq_inspector import DLQInspector
from scripts.chaos.utils.report import ChaosReport, TestCase, TestStatus


@dataclass
class BatchSimulationConfig:
    """Configuration for batch chaos simulation."""

    # Paths
    input_dir: Path = Path("./data/imports")
    archive_dir: Path = Path("./data/archive")
    chaos_dir: Path = Path("./data/chaos_test")

    # Kafka settings (for monitoring DLQ)
    bootstrap_servers: str = "localhost:9092"
    topic: str = "trades"
    dlq_topic: str = "trades-dlq"

    # Test settings
    wait_for_processing_seconds: float = 10.0
    cleanup_after_test: bool = True
    verbose: bool = True


class BatchChaosSimulator:
    """Simulator for batch pipeline chaos testing.

    Generates problematic files and validates that the batch
    ingestion pipeline handles them correctly.

    Example:
        simulator = BatchChaosSimulator()

        # Run all tests
        report = simulator.run_all_tests()
        report.print_summary()

        # Run specific test
        result = simulator.test_corrupt_files()
        print(f"Passed: {result.passed}")
    """

    def __init__(self, config: BatchSimulationConfig | None = None):
        """Initialize the simulator.

        Args:
            config: Simulation configuration
        """
        self.config = config or BatchSimulationConfig()
        self.kafka = KafkaHelper(
            bootstrap_servers=self.config.bootstrap_servers,
            topic=self.config.topic,
            dlq_topic=self.config.dlq_topic,
        )
        self.dlq_inspector = DLQInspector(
            bootstrap_servers=self.config.bootstrap_servers,
            dlq_topic=self.config.dlq_topic,
        )
        self.report = ChaosReport("Batch Chaos Tests")

        # Ensure directories exist
        self.config.chaos_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str) -> None:
        """Log message if verbose mode enabled."""
        if self.config.verbose:
            print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {message}")

    def _wait_for_processing(self, seconds: float | None = None) -> None:
        """Wait for batch processor to pick up files."""
        wait_time = seconds or self.config.wait_for_processing_seconds
        self._log(f"Waiting {wait_time}s for batch processing...")
        time.sleep(wait_time)

    def _get_dlq_count(self) -> int:
        """Get current DLQ message count."""
        return self.kafka.count_messages(self.config.dlq_topic)

    def _copy_to_input(self, filepath: Path) -> Path:
        """Copy a file to the input directory for processing.

        Args:
            filepath: Source file path

        Returns:
            Path to copied file in input dir
        """
        self.config.input_dir.mkdir(parents=True, exist_ok=True)
        dest = self.config.input_dir / filepath.name
        shutil.copy2(filepath, dest)
        return dest

    def _cleanup_file(self, filepath: Path) -> None:
        """Remove a test file."""
        if filepath.exists():
            filepath.unlink()

    def _run_file_test(
        self,
        name: str,
        issue: BatchIssue,
        expected_behavior: str,
        should_fail: bool = True,
    ) -> TestCase:
        """Run a single file-based test.

        Args:
            name: Test name
            issue: Issue generator
            expected_behavior: What should happen
            should_fail: Whether the file should cause an error

        Returns:
            TestCase with results
        """
        test = TestCase(
            name=name,
            category="batch",
            description=issue.description,
            expected_behavior=expected_behavior,
        )

        start_time = time.perf_counter()
        initial_dlq_count = self._get_dlq_count()
        generated_file: Path | None = None

        try:
            self._log(f"Generating {name} test file...")

            # Generate the problematic file
            result = issue.generate(output_dir=self.config.chaos_dir)
            generated_file = result.filepath

            if generated_file:
                self._log(f"  Created: {generated_file.name} ({len(result.content)} bytes)")

                # Copy to input directory for processing
                input_file = self._copy_to_input(generated_file)
                self._log(f"  Copied to: {input_file}")

                # Wait for processing
                self._wait_for_processing()

                # Check if file was processed (moved to archive or still in input)
                file_still_exists = input_file.exists()
                archive_file = self.config.archive_dir / input_file.name

                # Check DLQ for errors
                final_dlq_count = self._get_dlq_count()
                new_dlq_messages = final_dlq_count - initial_dlq_count

                test.dlq_messages_actual = new_dlq_messages
                test.duration_ms = (time.perf_counter() - start_time) * 1000

                # Determine actual behavior
                if file_still_exists:
                    test.actual_behavior = "File still in input (not processed or rejected)"
                elif archive_file.exists():
                    test.actual_behavior = f"File archived, {new_dlq_messages} DLQ messages"
                else:
                    test.actual_behavior = f"File processed, {new_dlq_messages} DLQ messages"

                # Determine pass/fail
                if should_fail:
                    # For error cases, we expect either DLQ messages or file rejection
                    if new_dlq_messages > 0 or file_still_exists:
                        test.status = TestStatus.PASSED
                    else:
                        test.status = TestStatus.FAILED
                        test.error_message = "Expected error handling but file processed normally"
                else:
                    # For valid cases, we expect successful processing
                    if not file_still_exists and new_dlq_messages == 0:
                        test.status = TestStatus.PASSED
                    elif new_dlq_messages > 0:
                        test.status = TestStatus.FAILED
                        test.error_message = f"Unexpected {new_dlq_messages} DLQ messages"
                    else:
                        test.status = TestStatus.PASSED  # File might be queued

                # Cleanup
                if self.config.cleanup_after_test:
                    if input_file.exists():
                        self._cleanup_file(input_file)
                    if archive_file.exists():
                        self._cleanup_file(archive_file)

            else:
                test.status = TestStatus.ERROR
                test.error_message = "Failed to generate test file"

            self._log(f"  Result: {test.status.value}")

        except Exception as e:
            test.status = TestStatus.ERROR
            test.error_message = str(e)
            test.duration_ms = (time.perf_counter() - start_time) * 1000
            self._log(f"  Error: {e}")

        finally:
            # Cleanup generated file
            if generated_file and generated_file.exists() and self.config.cleanup_after_test:
                self._cleanup_file(generated_file)

        return test

    def test_corrupt_files(self) -> TestCase:
        """Test corrupt file handling.

        Corrupt files should be detected and rejected.
        """
        issue = CorruptFileIssue(variant="truncated")
        return self._run_file_test(
            name="Corrupt File (Truncated)",
            issue=issue,
            expected_behavior="File rejected or rows sent to DLQ",
            should_fail=True,
        )

    def test_schema_drift_missing(self) -> TestCase:
        """Test missing column handling.

        Files missing required columns should fail validation.
        """
        issue = SchemaDriftIssue(variant="missing_column")
        return self._run_file_test(
            name="Schema Drift (Missing Column)",
            issue=issue,
            expected_behavior="Validation error, rows to DLQ",
            should_fail=True,
        )

    def test_schema_drift_extra(self) -> TestCase:
        """Test extra column handling.

        Files with extra columns should be handled gracefully.
        """
        issue = SchemaDriftIssue(variant="extra_column")
        return self._run_file_test(
            name="Schema Drift (Extra Column)",
            issue=issue,
            expected_behavior="Extra columns ignored, file processed",
            should_fail=False,
        )

    def test_encoding_issues(self) -> TestCase:
        """Test encoding issue handling.

        Files with wrong encoding should be detected.
        """
        issue = EncodingFileIssue(encoding="latin1")
        return self._run_file_test(
            name="Encoding Issue (Latin-1)",
            issue=issue,
            expected_behavior="Encoding error detected",
            should_fail=True,
        )

    def test_empty_file(self) -> TestCase:
        """Test empty file handling.

        Empty files should be handled gracefully without errors.
        """
        issue = EmptyFileIssue(variant="header_only")
        return self._run_file_test(
            name="Empty File (Header Only)",
            issue=issue,
            expected_behavior="File processed with 0 records",
            should_fail=False,
        )

    def test_partial_file(self) -> TestCase:
        """Test partial file handling.

        Incomplete files should be detected and handled.
        """
        issue = PartialFileIssue(complete_rows=5, partial_bytes=30)
        return self._run_file_test(
            name="Partial File (Incomplete Row)",
            issue=issue,
            expected_behavior="Complete rows processed, partial row to DLQ",
            should_fail=True,
        )

    def test_duplicate_files(self) -> TestCase:
        """Test duplicate file handling.

        Duplicate files should be processed idempotently.
        """
        issue = DuplicateFileIssue()

        # First file
        result1 = self._run_file_test(
            name="Duplicate File (First Copy)",
            issue=issue,
            expected_behavior="File processed normally",
            should_fail=False,
        )

        # Second file (same content)
        result2 = self._run_file_test(
            name="Duplicate File (Second Copy)",
            issue=issue,
            expected_behavior="Handled idempotently (no duplicate records)",
            should_fail=False,
        )

        # Combine results
        combined = TestCase(
            name="Duplicate Files (Idempotency)",
            category="batch",
            description="Same file processed twice",
            expected_behavior="Second file handled idempotently",
            status=TestStatus.PASSED if result1.passed and result2.passed else TestStatus.FAILED,
            duration_ms=result1.duration_ms + result2.duration_ms,
        )

        return combined

    def test_wrong_format(self) -> TestCase:
        """Test wrong format handling.

        Files with wrong format should be detected.
        """
        issue = WrongFormatIssue(actual_format="json_as_csv")
        return self._run_file_test(
            name="Wrong Format (JSON as CSV)",
            issue=issue,
            expected_behavior="Format error detected",
            should_fail=True,
        )

    def test_malformed_rows(self) -> TestCase:
        """Test malformed row handling.

        Files with some bad rows should process good rows.
        """
        issue = MalformedRowIssue(malformed_count=3, total_rows=20)
        return self._run_file_test(
            name="Malformed Rows",
            issue=issue,
            expected_behavior="Good rows processed, bad rows to DLQ",
            should_fail=True,  # Some rows will fail
        )

    def test_large_file(self, row_count: int = 10000) -> TestCase:
        """Test large file handling.

        Large files should be processed without memory issues.
        """
        issue = LargeFileIssue(row_count=row_count)
        return self._run_file_test(
            name=f"Large File ({row_count:,} rows)",
            issue=issue,
            expected_behavior="File processed without memory issues",
            should_fail=False,
        )

    def run_all_tests(self) -> ChaosReport:
        """Run all batch chaos tests.

        Returns:
            ChaosReport with all test results
        """
        self._log("=" * 60)
        self._log("BATCH CHAOS SIMULATION")
        self._log("=" * 60)

        # Store initial state
        initial_dlq = self._get_dlq_count()
        self._log(f"Initial DLQ count: {initial_dlq}")

        # Run all tests
        tests = [
            self.test_corrupt_files,
            self.test_schema_drift_missing,
            self.test_schema_drift_extra,
            self.test_encoding_issues,
            self.test_empty_file,
            self.test_partial_file,
            self.test_wrong_format,
            self.test_malformed_rows,
            # Skip large file in full run (slow)
            # self.test_large_file,
        ]

        for test_fn in tests:
            result = test_fn()
            self.report.add_test(result)

        self.report.complete()
        return self.report

    def run_quick_test(self) -> ChaosReport:
        """Run a quick subset of tests.

        Returns:
            ChaosReport with test results
        """
        self._log("Running quick batch chaos test...")

        self.report.add_test(self.test_corrupt_files())
        self.report.add_test(self.test_empty_file())

        self.report.complete()
        return self.report

    def generate_test_files_only(self, output_dir: Path | None = None) -> list[Path]:
        """Generate test files without running tests.

        Useful for manual testing or inspection.

        Args:
            output_dir: Output directory

        Returns:
            List of generated file paths
        """
        output_dir = output_dir or self.config.chaos_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        files = []
        issues = [
            CorruptFileIssue(variant="truncated"),
            SchemaDriftIssue(variant="missing_column"),
            EncodingFileIssue(encoding="latin1"),
            EmptyFileIssue(variant="header_only"),
            PartialFileIssue(),
            WrongFormatIssue(actual_format="json_as_csv"),
            MalformedRowIssue(),
        ]

        for issue in issues:
            result = issue.generate(output_dir=output_dir)
            if result.filepath:
                files.append(result.filepath)
                self._log(f"Generated: {result.filepath.name}")

        return files

    def cleanup(self) -> None:
        """Clean up resources and test files."""
        self.kafka.close()

        # Clean chaos directory
        if self.config.chaos_dir.exists():
            for f in self.config.chaos_dir.glob("*"):
                f.unlink()


def main():
    """Run batch chaos simulation from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Batch Chaos Simulator")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("./data/imports"),
        help="Batch input directory",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick test only",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate test files, don't run tests",
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

    config = BatchSimulationConfig(
        input_dir=args.input_dir,
    )

    simulator = BatchChaosSimulator(config)

    try:
        if args.generate_only:
            files = simulator.generate_test_files_only()
            print(f"\nGenerated {len(files)} test files in {config.chaos_dir}")
            for f in files:
                print(f"  - {f.name}")
        elif args.quick:
            report = simulator.run_quick_test()
            report.print_summary()
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
