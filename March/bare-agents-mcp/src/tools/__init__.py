"""Tool registry for the MCP server.

Tools self-register on import via the @register_tool decorator.
The server imports tool modules at startup to populate the registry.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger()


@dataclass
class ToolDef:
    """A registered tool: its metadata + handler function."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., str]


# Global registry — populated by @register_tool decorators at import time.
_REGISTRY: dict[str, ToolDef] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any],
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Decorator that registers a function as an MCP tool."""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        _REGISTRY[name] = ToolDef(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=fn,
        )
        return fn

    return decorator


def get_all_definitions() -> list[dict[str, Any]]:
    """Return all tool definitions in MCP tools/list format."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "inputSchema": t.input_schema,
        }
        for t in _REGISTRY.values()
    ]


def execute(name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
    """Execute a tool by name. Returns (result_text, is_error)."""
    tool = _REGISTRY.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'", True
    try:
        return tool.handler(**arguments), False
    except Exception:
        return f"Error executing {name}: {traceback.format_exc()}", True
