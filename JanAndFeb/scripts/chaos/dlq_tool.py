#!/usr/bin/env python3
"""DLQ Management Tool.

Inspect, analyze, and replay Dead Letter Queue messages.

Usage:
    # View DLQ summary
    python scripts/chaos/dlq_tool.py inspect

    # View detailed entries
    python scripts/chaos/dlq_tool.py inspect --detailed

    # Export to JSON
    python scripts/chaos/dlq_tool.py export dlq_entries.json

    # View by error type
    python scripts/chaos/dlq_tool.py inspect --error-type ValidationError

    # Replay a fixed message
    python scripts/chaos/dlq_tool.py replay --file fixed_message.json

    # Clear DLQ (for testing)
    python scripts/chaos/dlq_tool.py clear --confirm
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.chaos.utils.dlq_inspector import DLQInspector
from scripts.chaos.utils.kafka_helper import KafkaHelper


def cmd_inspect(args):
    """Inspect DLQ contents."""
    inspector = DLQInspector(
        bootstrap_servers=args.bootstrap_servers,
        dlq_topic=args.dlq_topic,
    )

    inspector.load_entries(max_entries=args.limit)

    if args.error_type:
        entries = inspector.get_entries(error_type=args.error_type)
        print(f"\nFiltered to error type: {args.error_type}")
        print(f"Found {len(entries)} entries")
        print("-" * 60)

        for i, entry in enumerate(entries[:20], 1):
            print(f"\n{i}. Partition {entry.partition}, Offset {entry.offset}")
            print(f"   Time: {entry.failed_at}")
            print(f"   Error: {entry.error_message[:100]}")
            if args.detailed:
                print(f"   Original: {entry.original_message[:200]}...")
    else:
        inspector.print_report()

        if args.detailed:
            print("\n" + "=" * 60)
            print("DETAILED ENTRIES (first 20)")
            print("=" * 60)

            for i, entry in enumerate(inspector.get_entries(limit=20), 1):
                print(f"\n{i}. [{entry.error_type}]")
                print(f"   Time: {entry.failed_at}")
                print(f"   Consumer: {entry.consumer_group}")
                print(f"   Error: {entry.error_message}")
                print(f"   Original: {entry.original_message[:200]}")
                if len(entry.original_message) > 200:
                    print("   ...")
                print(f"   Fix suggestion: {entry.get_fix_suggestion()}")


def cmd_export(args):
    """Export DLQ entries to file."""
    inspector = DLQInspector(
        bootstrap_servers=args.bootstrap_servers,
        dlq_topic=args.dlq_topic,
    )

    inspector.load_entries(max_entries=args.limit)
    inspector.export_to_json(args.output_file)

    summary = inspector.get_summary()
    print(f"Exported {summary.total_messages} DLQ entries to: {args.output_file}")


def cmd_replay(args):
    """Replay fixed messages to main topic."""
    inspector = DLQInspector(
        bootstrap_servers=args.bootstrap_servers,
        dlq_topic=args.dlq_topic,
        main_topic=args.topic,
    )

    if args.file:
        # Read messages from file
        with open(args.file) as f:
            messages = json.load(f)

        if isinstance(messages, dict):
            messages = [messages]

        print(f"Replaying {len(messages)} messages to {args.topic}...")

        success, failure = inspector.replay_messages(messages)
        print(f"Results: {success} succeeded, {failure} failed")

    else:
        print("Error: --file is required for replay")
        return 1

    return 0


def cmd_clear(args):
    """Clear DLQ topic (for testing)."""
    if not args.confirm:
        print("ERROR: Must specify --confirm to clear DLQ")
        print("This will delete all messages in the DLQ topic!")
        return 1

    helper = KafkaHelper(
        bootstrap_servers=args.bootstrap_servers,
        dlq_topic=args.dlq_topic,
    )

    count_before = helper.count_messages(args.dlq_topic)
    print(f"Current DLQ message count: {count_before}")

    if count_before == 0:
        print("DLQ is already empty")
        return 0

    print(f"Clearing DLQ topic: {args.dlq_topic}")

    if helper.clear_topic(args.dlq_topic):
        print("DLQ cleared successfully")
    else:
        print("Failed to clear DLQ")
        return 1

    return 0


def cmd_count(args):
    """Count messages in topics."""
    helper = KafkaHelper(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
        dlq_topic=args.dlq_topic,
    )

    main_count = helper.count_messages(args.topic)
    dlq_count = helper.count_messages(args.dlq_topic)

    print(f"Topic '{args.topic}': {main_count:,} messages")
    print(f"Topic '{args.dlq_topic}': {dlq_count:,} messages")

    if dlq_count > 0:
        ratio = dlq_count / (main_count + dlq_count) * 100 if main_count > 0 else 100
        print(f"DLQ ratio: {ratio:.2f}%")


def main():
    parser = argparse.ArgumentParser(
        description="DLQ Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers",
    )
    parser.add_argument(
        "--topic",
        default="trades",
        help="Main topic name",
    )
    parser.add_argument(
        "--dlq-topic",
        default="trades-dlq",
        help="DLQ topic name",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect DLQ contents")
    inspect_parser.add_argument(
        "--detailed", "-d",
        action="store_true",
        help="Show detailed entries",
    )
    inspect_parser.add_argument(
        "--error-type", "-e",
        help="Filter by error type",
    )
    inspect_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=1000,
        help="Max entries to load",
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export DLQ to file")
    export_parser.add_argument(
        "output_file",
        help="Output JSON file",
    )
    export_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10000,
        help="Max entries to export",
    )

    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay fixed messages")
    replay_parser.add_argument(
        "--file", "-f",
        required=True,
        help="JSON file with messages to replay",
    )

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear DLQ (testing only)")
    clear_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm clearing DLQ",
    )

    # Count command
    count_parser = subparsers.add_parser("count", help="Count messages in topics")

    args = parser.parse_args()

    if args.command == "inspect":
        return cmd_inspect(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "replay":
        return cmd_replay(args)
    elif args.command == "clear":
        return cmd_clear(args)
    elif args.command == "count":
        return cmd_count(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
