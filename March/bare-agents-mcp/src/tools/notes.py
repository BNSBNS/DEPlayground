"""In-memory notes tools: create, list, and search notes."""

from __future__ import annotations

import json
from typing import Any

from src.tools import register_tool

# Module-level state — persists for the lifetime of the MCP server process.
_notes: list[dict[str, Any]] = []
_next_id: int = 0


@register_tool(
    name="create_note",
    description="Create a new note with a title and content.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Note title"},
            "content": {"type": "string", "description": "Note content"},
        },
        "required": ["title", "content"],
    },
)
def create_note(title: str, content: str) -> str:
    global _next_id  # noqa: PLW0603
    _next_id += 1
    note = {"id": _next_id, "title": title, "content": content}
    _notes.append(note)
    return f"Created note #{note['id']}: {title}"


@register_tool(
    name="list_notes",
    description="List all notes. Returns a JSON array.",
    input_schema={
        "type": "object",
        "properties": {},
    },
)
def list_notes() -> str:
    return json.dumps(_notes, indent=2)


@register_tool(
    name="search_notes",
    description="Search notes by keyword in title or content. Returns a JSON array.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword"},
        },
        "required": ["query"],
    },
)
def search_notes(query: str) -> str:
    q = query.lower()
    matches = [n for n in _notes if q in n["title"].lower() or q in n["content"].lower()]
    return json.dumps(matches, indent=2)
