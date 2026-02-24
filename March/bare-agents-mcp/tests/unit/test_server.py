"""Tests for the MCP server message handling."""

from __future__ import annotations

import json
from io import StringIO
from typing import Any
from unittest.mock import patch

from src.server import handle_message, send_error, send_response


def _capture_stdout(fn: Any, *args: Any) -> dict[str, Any]:
    """Call fn with stdout captured, return parsed JSON response."""
    buf = StringIO()
    with patch("sys.stdout", buf):
        fn(*args)
    return json.loads(buf.getvalue().strip())


class TestSendResponse:
    def test_success_response_format(self) -> None:
        resp = _capture_stdout(send_response, 1, {"key": "value"})
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"] == {"key": "value"}

    def test_error_response_format(self) -> None:
        method_not_found = -32601
        resp = _capture_stdout(send_error, 2, method_not_found, "Method not found")
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 2
        assert resp["error"]["code"] == method_not_found
        assert resp["error"]["message"] == "Method not found"


class TestHandleMessage:
    def test_initialize(self) -> None:
        resp = _capture_stdout(
            handle_message,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0.0"},
                },
            },
        )
        result = resp["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "bare-mcp"

    def test_initialized_notification(self) -> None:
        # Should not raise or produce output (it's a notification).
        buf = StringIO()
        with patch("sys.stdout", buf):
            handle_message({"jsonrpc": "2.0", "method": "initialized"})
        assert buf.getvalue().strip() == ""

    def test_tools_list(self) -> None:
        resp = _capture_stdout(
            handle_message,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        tools = resp["result"]["tools"]
        assert isinstance(tools, list)
        assert len(tools) > 0
        names = {t["name"] for t in tools}
        assert "read_file" in names
        assert "create_note" in names

    def test_tools_call_success(self) -> None:
        resp = _capture_stdout(
            handle_message,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_notes", "arguments": {}},
            },
        )
        result = resp["result"]
        assert result["content"][0]["type"] == "text"
        assert "isError" not in result

    def test_tools_call_unknown_tool(self) -> None:
        resp = _capture_stdout(
            handle_message,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "nonexistent", "arguments": {}},
            },
        )
        result = resp["result"]
        assert result["isError"] is True
        assert "unknown tool" in result["content"][0]["text"]

    def test_unknown_method(self) -> None:
        resp = _capture_stdout(
            handle_message,
            {"jsonrpc": "2.0", "id": 5, "method": "unknown/method"},
        )
        assert "error" in resp
        method_not_found = -32601
        assert resp["error"]["code"] == method_not_found
