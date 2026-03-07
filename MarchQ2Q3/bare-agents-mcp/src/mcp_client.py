"""Minimal async MCP client — spawns a server subprocess and speaks JSON-RPC over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import structlog

logger = structlog.get_logger()

CLIENT_INFO = {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "bare-agent", "version": "1.0.0"},
}

REQUEST_TIMEOUT = 30.0  # seconds


class ToolError(Exception):
    """Raised when an MCP tool execution returns isError: true."""


class McpClient:
    """Async MCP client that manages a server subprocess over stdio."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._next_id: int = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None

    def _require_process(self) -> asyncio.subprocess.Process:
        """Return the subprocess or raise if not started."""
        if self._process is None:
            raise RuntimeError("McpClient not started — call start() first")
        return self._process

    async def start(self, cmd: list[str]) -> None:
        """Spawn the MCP server subprocess."""
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._reader_loop())
        # Also drain stderr in background so the server's logs don't block.
        self._stderr_task = asyncio.create_task(self._stderr_loop())
        logger.info("client_spawned", cmd=cmd, pid=self._process.pid)

    async def _reader_loop(self) -> None:
        """Read stdout line-by-line, resolve pending futures."""
        proc = self._require_process()
        if not proc.stdout:
            raise RuntimeError("Server subprocess has no stdout pipe")
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode().strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("client_bad_json", line=line[:100])
                continue

            logger.debug("client_recv", msg=msg)

            # Route responses to pending futures by ID.
            msg_id = msg.get("id")
            if msg_id is not None and msg_id in self._pending:
                future = self._pending.pop(msg_id)
                if "error" in msg:
                    future.set_exception(RuntimeError(json.dumps(msg["error"])))
                else:
                    future.set_result(msg.get("result", {}))

        # Server stdout closed — reject any pending futures so callers don't hang.
        for _msg_id, future in self._pending.items():
            if not future.done():
                future.set_exception(ConnectionError("MCP server process exited"))
        self._pending.clear()

    async def _stderr_loop(self) -> None:
        """Forward server stderr to our stderr for visibility."""
        proc = self._require_process()
        if not proc.stderr:
            raise RuntimeError("Server subprocess has no stderr pipe")
        while True:
            raw = await proc.stderr.readline()
            if not raw:
                break
            print(f"[server] {raw.decode().rstrip()}", file=sys.stderr)

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and await the response (with timeout)."""
        proc = self._require_process()
        if not proc.stdin:
            raise RuntimeError("Server subprocess has no stdin pipe")
        self._next_id += 1
        msg_id = self._next_id
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            msg["params"] = params

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[msg_id] = future

        line = json.dumps(msg) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()
        logger.debug("client_sent", msg=msg)

        return await asyncio.wait_for(future, timeout=REQUEST_TIMEOUT)

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        proc = self._require_process()
        if not proc.stdin:
            raise RuntimeError("Server subprocess has no stdin pipe")
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params

        line = json.dumps(msg) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()
        logger.debug("client_sent_notification", method=method)

    async def initialize(self) -> dict[str, Any]:
        """Perform the MCP initialize handshake."""
        result = await self._send_request("initialize", CLIENT_INFO)
        await self._send_notification("initialized")
        logger.info("mcp_initialized", server_info=result.get("serverInfo"))
        return result  # type: ignore[no-any-return]

    async def list_tools(self) -> list[dict[str, Any]]:
        """Get all available tools from the server."""
        result = await self._send_request("tools/list")
        tools: list[dict[str, Any]] = result.get("tools", [])
        logger.info("tools_discovered", count=len(tools))
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return the text result.

        Raises ToolError if the server indicates the tool execution failed.
        """
        result = await self._send_request("tools/call", {"name": name, "arguments": arguments})
        # Extract text from the content array.
        content = result.get("content", [])
        texts = [c["text"] for c in content if c.get("type") == "text"]
        text = "\n".join(texts)

        if result.get("isError"):
            raise ToolError(text)

        return text

    async def close(self) -> None:
        """Terminate the server subprocess."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
            logger.info("client_closed")
        for task in (self._reader_task, self._stderr_task):
            if task:
                task.cancel()
