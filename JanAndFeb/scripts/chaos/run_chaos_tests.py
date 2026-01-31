#!/usr/bin/env python3
"""Comprehensive Chaos Test Runner.

Runs both streaming and batch chaos tests to validate
pipeline resilience against common data issues.

Usage:
    # Run all tests
    python scripts/chaos/run_chaos_tests.py

    # Run streaming tests only
    python scripts/chaos/run_chaos_tests.py --streaming

    # Run batch tests only
    python scripts/chaos/run_chaos_tests.py --batch

    # Quick test (subset)
    python scripts/chaos/run_chaos_tests.py --quick

    # Export report
    python scripts/chaos/run_chaos_tests.py --output report.json

    # Inspect DLQ only
    python scripts/chaos/run_chaos_tests.py --dlq-inspect
"""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.chaos.streaming.simulator import StreamingChaosSimulator, SimulationConfig
from scripts.chaos.batch.simulator import BatchChaosSimulator, BatchSimulationConfig
from scripts.chaos.utils.dlq_inspector import DLQInspector
from scripts.chaos.utils.report import ChaosReport, TestStatus


def print_banner():
    """Print a nice banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                      CHAOS TESTING FRAMEWORK                         ║
║                                                                      ║
║  Testing pipeline resilience against common data issues              ║
║  - Streaming: Poison pills, schema errors, duplicates, late events  ║
║  - Batch: Corrupt files, encoding issues, schema drift              ║
╚══════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def run_streaming_tests(
    bootstrap_servers: str,
    topic: str,
    quick: bool = False,
) -> ChaosReport:
    """Run streaming chaos tests.

    Args:
        bootstrap_servers: Kafka servers
        topic: Main topic
        quick: Run quick tests only

    Returns:
        ChaosReport with results
    """
    print("\n" + "=" * 70)
    print("STREAMING CHAOS TESTS")
    print("=" * 70)

    config = SimulationConfig(
        bootstrap_servers=bootstrap_servers,
        topic=topic,
    )

    simulator = StreamingChaosSimulator(config)

    try:
        if quick:
            return simulator.run_quick_test()
        else:
            return simulator.run_all_tests()
    finally:
        simulator.cleanup()


def run_batch_tests(
    input_dir: Path,
    bootstrap_servers: str,
    quick: bool = False,
) -> ChaosReport:
    """Run batch chaos tests.

    Args:
        input_dir: Batch input directory
        bootstrap_servers: Kafka servers
        quick: Run quick tests only

    Returns:
        ChaosReport with results
    """
    print("\n" + "=" * 70)
    print("BATCH CHAOS TESTS")
    print("=" * 70)

    config = BatchSimulationConfig(
        input_dir=input_dir,
        bootstrap_servers=bootstrap_servers,
    )

    simulator = BatchChaosSimulator(config)

    try:
        if quick:
            return simulator.run_quick_test()
        else:
            return simulator.run_all_tests()
    finally:
        simulator.cleanup()


def inspect_dlq(bootstrap_servers: str, dlq_topic: str) -> None:
    """Inspect the DLQ and print report.

    Args:
        bootstrap_servers: Kafka servers
        dlq_topic: DLQ topic name
    """
    print("\n" + "=" * 70)
    print("DLQ INSPECTION")
    print("=" * 70)

    inspector = DLQInspector(
        bootstrap_servers=bootstrap_servers,
        dlq_topic=dlq_topic,
    )

    inspector.load_entries()
    inspector.print_report()


def combine_reports(reports: list[ChaosReport]) -> ChaosReport:
    """Combine multiple reports into one.

    Args:
        reports: List of reports to combine

    Returns:
        Combined ChaosReport
    """
    combined = ChaosReport("Combined Chaos Test Report")

    for report in reports:
        for test in report.tests:
            combined.add_test(test)

    combined.complete()
    return combined


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Chaos Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all chaos tests
  python scripts/chaos/run_chaos_tests.py

  # Run only streaming tests
  python scripts/chaos/run_chaos_tests.py --streaming

  # Run only batch tests
  python scripts/chaos/run_chaos_tests.py --batch

  # Run quick tests (subset)
  python scripts/chaos/run_chaos_tests.py --quick

  # Export detailed report
  python scripts/chaos/run_chaos_tests.py --output chaos_report.json --detailed

  # Just inspect the DLQ
  python scripts/chaos/run_chaos_tests.py --dlq-inspect
        """,
    )

    # Test selection
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Run streaming tests only",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch tests only",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick subset of tests",
    )

    # Infrastructure settings
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers (default: localhost:9092)",
    )
    parser.add_argument(
        "--topic",
        default="trades",
        help="Main Kafka topic (default: trades)",
    )
    parser.add_argument(
        "--dlq-topic",
        default="trades-dlq",
        help="DLQ topic (default: trades-dlq)",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("./data/imports"),
        help="Batch input directory (default: ./data/imports)",
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        help="Output report file (.json or .md)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Print detailed test results",
    )

    # Utilities
    parser.add_argument(
        "--dlq-inspect",
        action="store_true",
        help="Only inspect DLQ, don't run tests",
    )
    parser.add_argument(
        "--dlq-export",
        help="Export DLQ entries to JSON file",
    )

    args = parser.parse_args()

    print_banner()

    # DLQ inspection mode
    if args.dlq_inspect:
        inspect_dlq(args.bootstrap_servers, args.dlq_topic)
        return 0

    # DLQ export mode
    if args.dlq_export:
        inspector = DLQInspector(
            bootstrap_servers=args.bootstrap_servers,
            dlq_topic=args.dlq_topic,
        )
        inspector.load_entries()
        inspector.export_to_json(args.dlq_export)
        print(f"DLQ entries exported to: {args.dlq_export}")
        return 0

    # Determine which tests to run
    run_streaming = args.streaming or (not args.streaming and not args.batch)
    run_batch = args.batch or (not args.streaming and not args.batch)

    reports = []

    # Run selected tests
    if run_streaming:
        report = run_streaming_tests(
            bootstrap_servers=args.bootstrap_servers,
            topic=args.topic,
            quick=args.quick,
        )
        reports.append(report)

    if run_batch:
        report = run_batch_tests(
            input_dir=args.input_dir,
            bootstrap_servers=args.bootstrap_servers,
            quick=args.quick,
        )
        reports.append(report)

    # Combine reports
    if len(reports) > 1:
        final_report = combine_reports(reports)
    elif reports:
        final_report = reports[0]
    else:
        print("No tests were run!")
        return 1

    # Print results
    print("\n")
    if args.detailed:
        final_report.print_detailed()
    else:
        final_report.print_summary()

    # Export if requested
    if args.output:
        if args.output.endswith(".md"):
            final_report.export_markdown(args.output)
        else:
            final_report.export_json(args.output)
        print(f"\nReport exported to: {args.output}")

    # Return exit code based on test results
    if final_report.failed_tests > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
