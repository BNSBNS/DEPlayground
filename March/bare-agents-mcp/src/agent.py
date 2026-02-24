"""Raw agent loop — calls Claude API, executes tools via MCP, feeds results back.

Usage:
    python -m src.agent "Your question here"
    python -m src.agent  # interactive mode
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import anthropic
import structlog

from src.mcp_client import McpClient, ToolError

# Configure structlog to stderr.
structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)
logger = structlog.get_logger()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "4096"))
MAX_ITERATIONS = int(os.environ.get("AGENT_MAX_ITERATIONS", "20"))


def mcp_to_anthropic_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to Anthropic API format.

    Only difference: MCP uses 'inputSchema', Anthropic uses 'input_schema'.
    """
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["inputSchema"],
        }
        for t in mcp_tools
    ]


def serialize_content(content: list[Any]) -> list[dict[str, Any]]:
    """Serialize Anthropic SDK content blocks to plain dicts for the messages list."""
    result: list[dict[str, Any]] = []
    for block in content:
        if hasattr(block, "model_dump"):
            result.append(block.model_dump())
        elif isinstance(block, dict):
            result.append(block)
        else:
            result.append({"type": "text", "text": str(block)})
    return result


async def run_agent(query: str) -> None:
    """Run the agent loop for a single query."""
    # 1. Spawn MCP server and initialize.
    client = McpClient()
    await client.start([sys.executable, "-m", "src.server"])
    try:
        await client.initialize()

        # 2. Discover tools.
        mcp_tools = await client.list_tools()
        tools = mcp_to_anthropic_tools(mcp_tools)
        logger.info("agent_ready", tools=[t["name"] for t in tools])

        # 3. Create Anthropic client.
        api = anthropic.Anthropic()

        # 4. Agent loop.
        messages: list[dict[str, Any]] = [{"role": "user", "content": query}]
        iteration = 0

        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info("loop_iteration", n=iteration)

            response = api.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                tools=tools,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            logger.info(
                "api_response",
                stop_reason=response.stop_reason,
                content_types=[b.type for b in response.content],
            )

            # Final answer — print text blocks and exit.
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        print(block.text)
                break

            # Tool use — execute each tool via MCP, collect results.
            if response.stop_reason == "tool_use":
                # CRITICAL: append the ENTIRE response.content as the assistant message.
                messages.append(
                    {
                        "role": "assistant",
                        "content": serialize_content(response.content),
                    }
                )

                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info("executing_tool", tool=block.name, input=block.input)
                        try:
                            result_text = await client.call_tool(block.name, block.input)
                        except ToolError as exc:
                            result_text = str(exc)
                            logger.warning("tool_error", tool=block.name, error=result_text[:200])
                        logger.info("tool_result", tool=block.name, result=result_text[:200])
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_text,
                            }
                        )

                # Append all tool results as a single user message.
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason.
            logger.warning("unexpected_stop", stop_reason=response.stop_reason)
            break
        else:
            logger.error("max_iterations_reached", limit=MAX_ITERATIONS)
    finally:
        await client.close()


def main() -> None:
    """Entry point — get query from args or prompt."""
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your question: ")

    asyncio.run(run_agent(query))


if __name__ == "__main__":
    main()
