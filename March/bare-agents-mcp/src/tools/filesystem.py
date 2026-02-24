"""Filesystem tools: read, write, and list directory contents.

Security: All paths are resolved and validated against SANDBOX_ROOT (env var,
defaults to cwd). Paths that escape the sandbox are rejected. Symlinks that
resolve outside the sandbox are also rejected. Reads are capped at MAX_FILE_SIZE.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.tools import register_tool

SANDBOX_ROOT = Path(os.environ.get("SANDBOX_ROOT", ".")).resolve()
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10 MB default


def _safe_path(path: str) -> Path:
    """Resolve *path* and verify it stays within SANDBOX_ROOT."""
    resolved = (SANDBOX_ROOT / path).resolve()
    if not resolved.is_relative_to(SANDBOX_ROOT):
        raise PermissionError(f"Path escapes sandbox: {path}")
    return resolved


@register_tool(
    name="read_file",
    description="Read the contents of a file at the given path (sandboxed).",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
        },
        "required": ["path"],
    },
)
def read_file(path: str) -> str:
    p = _safe_path(path)
    size = p.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large ({size} bytes, limit {MAX_FILE_SIZE})")
    return p.read_text(encoding="utf-8")


@register_tool(
    name="write_file",
    description="Write content to a file at the given path (sandboxed). Creates parent dirs.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str) -> str:
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {path}"


@register_tool(
    name="list_directory",
    description="List all entries in a directory (sandboxed).",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list"},
        },
        "required": ["path"],
    },
)
def list_directory(path: str) -> str:
    p = _safe_path(path)
    entries = [e.name for e in sorted(p.iterdir())]
    return json.dumps(entries)
