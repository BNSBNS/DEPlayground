"""Bare MCP server — JSON-RPC 2.0 over stdio.

Reads newline-delimited JSON from stdin, writes responses to stdout.
All debug logging goes to stderr (doesn't interfere with the protocol).
"""

from __future__ import annotations

import json
import sys
from typing import Any

import structlog

# Configure structlog to write to stderr so stdout stays clean for JSON-RPC.
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)
logger = structlog.get_logger()

# Import tool modules — triggers self-registration via @register_tool decorators.
import src.tools.filesystem  # noqa: E402
import src.tools.notes  # noqa: E402, F401
from src.tools import execute, get_all_definitions  # noqa: E402

SERVER_INFO = {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "bare-mcp", "version": "1.0.0"},
}

_METHOD_NOT_FOUND = -32601


def send_response(msg_id: int | str | None, result: Any) -> None:
    """Write a JSON-RPC success response to stdout."""
    response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    logger.debug("sent", response=response)


def send_error(msg_id: int | str | None, code: int, message: str) -> None:
    """Write a JSON-RPC error response to stdout."""
    response = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    }
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    logger.error("sent_error", response=response)


def handle_message(msg: dict[str, Any]) -> None:
    """Dispatch a single JSON-RPC message."""
    method = msg.get("method", "")
    msg_id = msg.get("id")  # None for notifications
    params = msg.get("params", {})

    logger.debug("received", method=method, id=msg_id)

    if method == "initialize":
        send_response(msg_id, SERVER_INFO)

    elif method == "initialized":
        # Notification — no response needed.
        logger.info("handshake_complete")

    elif method == "tools/list":
        send_response(msg_id, {"tools": get_all_definitions()})

    elif method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        logger.info("tool_call", tool=name, arguments=arguments)

        result_text, is_error = execute(name, arguments)

        result: dict[str, Any] = {
            "content": [{"type": "text", "text": result_text}],
        }
        if is_error:
            result["isError"] = True

        send_response(msg_id, result)

    elif msg_id is not None:
        send_error(msg_id, _METHOD_NOT_FOUND, f"Method not found: {method}")
    else:
        logger.warning("unknown_notification", method=method)


def main() -> None:
    """Read stdin line by line, dispatch each JSON-RPC message."""
    logger.info("server_started", tools=len(get_all_definitions()))

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            logger.error("invalid_json", line=line[:100])
            continue

        handle_message(msg)


if __name__ == "__main__":
    main()
