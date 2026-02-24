"""Raw agent loop using a local Ollama instance instead of Anthropic API.

Ollama exposes an OpenAI-compatible API. We use httpx to call it directly,
keeping the same MCP tool execution pattern as agent.py.

Usage:
    python -m src.agent_ollama "Your question here"
    python -m src.agent_ollama  # interactive mode

Requires:
    - Ollama running locally (default: http://localhost:11434)
    - A model with tool-use support pulled (e.g., `ollama pull qwen2.5`)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import httpx
import structlog

from src.mcp_client import McpClient

structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)
logger = structlog.get_logger()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5")
MAX_ITERATIONS = 20


def mcp_to_openai_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to OpenAI function-calling format.

    Ollama's /api/chat endpoint uses the OpenAI tool schema:
    { type: "function", function: { name, description, parameters } }
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        }
        for t in mcp_tools
    ]


async def run_agent(query: str) -> None:
    """Run the agent loop for a single query using Ollama."""
    # 1. Spawn MCP server and initialize.
    client = McpClient()
    await client.start([sys.executable, "-m", "src.server"])
    await client.initialize()

    # 2. Discover tools.
    mcp_tools = await client.list_tools()
    tools = mcp_to_openai_tools(mcp_tools)
    logger.info("agent_ready", tools=[t["function"]["name"] for t in tools])

    # 3. Agent loop.
    messages: list[dict[str, Any]] = [{"role": "user", "content": query}]
    iteration = 0

    async with httpx.AsyncClient(base_url=OLLAMA_BASE_URL, timeout=120.0) as http:
        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info("loop_iteration", n=iteration)

            payload: dict[str, Any] = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "tools": tools,
                "stream": False,
            }

            resp = await http.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

            assistant_msg = data["message"]
            tool_calls: list[dict[str, Any]] = assistant_msg.get("tool_calls") or []

            logger.info(
                "api_response",
                has_tool_calls=bool(tool_calls),
                content_preview=str(assistant_msg.get("content", ""))[:100],
            )

            # No tool calls — final answer.
            if not tool_calls:
                print(assistant_msg.get("content", ""))
                break

            # Append assistant message (with tool_calls) to history.
            messages.append(assistant_msg)

            # Execute each tool call via MCP.
            for tc in tool_calls:
                fn = tc["function"]
                tool_name = fn["name"]
                # Ollama may return arguments as string or dict.
                tool_args = fn.get("arguments", {})
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)

                logger.info("executing_tool", tool=tool_name, input=tool_args)
                result_text = await client.call_tool(tool_name, tool_args)
                logger.info("tool_result", tool=tool_name, result=result_text[:200])

                # Append tool result in OpenAI format.
                messages.append(
                    {
                        "role": "tool",
                        "content": result_text,
                    }
                )
        else:
            logger.error("max_iterations_reached", limit=MAX_ITERATIONS)

    await client.close()


def main() -> None:
    """Entry point — get query from args or prompt."""
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your question: ")

    asyncio.run(run_agent(query))


if __name__ == "__main__":
    main()
