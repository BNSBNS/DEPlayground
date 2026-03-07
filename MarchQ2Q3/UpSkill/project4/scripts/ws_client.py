#!/usr/bin/env python
"""WebSocket CLI client — connect to the real-time streaming API and display live events.

Usage:
    python scripts/ws_client.py             # stream live sales (default)
    python scripts/ws_client.py events      # stream raw events
    python scripts/ws_client.py sales --pretty --host localhost --port 8040

Prerequisites:
    pip install websockets   (usually pre-installed as a FastAPI/starlette dependency)
    make docker-up           (stack must be running)
    make simulate            (in a separate terminal, to generate events)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

STREAMS = {
    "sales": "/ws/sales",
    "events": "/ws/events",
}

STREAM_DESCRIPTIONS = {
    "sales": "aggregated sales windows (1m / 5m / 1h)",
    "events": "raw events (orders, payments, clicks, inventory)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream real-time events from the analytics API via WebSocket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {k}: {v}" for k, v in STREAM_DESCRIPTIONS.items()
        ),
    )
    parser.add_argument(
        "stream",
        nargs="?",
        choices=list(STREAMS),
        default="sales",
        help="Which stream to subscribe to (default: sales)",
    )
    parser.add_argument("--host", default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", type=int, default=8040, help="API port (default: 8040)")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Stop after receiving N messages (0 = unlimited)",
    )
    return parser.parse_args()


def format_message(raw: str, pretty: bool) -> str:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    try:
        data = json.loads(raw)
        body = json.dumps(data, indent=2, default=str) if pretty else json.dumps(data, default=str)
    except json.JSONDecodeError:
        body = raw
    return f"[{ts}] {body}"


async def stream(url: str, pretty: bool, max_count: int) -> None:
    try:
        import websockets  # noqa: PLC0415
    except ImportError:
        print("ERROR: websockets package not found. Run: pip install websockets")
        sys.exit(1)

    print(f"Connecting to {url} ...", flush=True)
    try:
        async with websockets.connect(url) as ws:  # type: ignore[attr-defined]
            print(f"Connected. Streaming events (Ctrl+C to stop)\n{'─' * 60}", flush=True)
            received = 0
            async for raw in ws:
                print(format_message(str(raw), pretty), flush=True)
                received += 1
                if max_count and received >= max_count:
                    print(f"\nReceived {received} messages. Exiting.")
                    break
    except ConnectionRefusedError:
        print(f"\nERROR: Could not connect to {url}")
        print("Checklist:")
        print("  1. make docker-up   (start the stack)")
        print("  2. make simulate    (in a separate terminal)")
        print(f"  3. Confirm API is on port {url.split(':')[2].split('/')[0]}")
        sys.exit(1)
    except OSError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)


def main() -> None:
    args = parse_args()
    path = STREAMS[args.stream]
    url = f"ws://{args.host}:{args.port}{path}"

    print(f"Stream : {args.stream} — {STREAM_DESCRIPTIONS[args.stream]}")
    print(f"URL    : {url}")
    print(f"Format : {'pretty JSON' if args.pretty else 'compact JSON'}")
    if args.count:
        print(f"Limit  : {args.count} messages")
    print()

    try:
        asyncio.run(stream(url, args.pretty, args.count))
    except KeyboardInterrupt:
        print("\nDisconnected.")


if __name__ == "__main__":
    main()
