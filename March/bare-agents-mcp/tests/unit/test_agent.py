"""Tests for agent helper functions (no API calls needed)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.agent import mcp_to_anthropic_tools, serialize_content


class TestMcpToAnthropicTools:
    def test_schema_key_conversion(self) -> None:
        mcp_tools = [
            {
                "name": "read_file",
                "description": "Read a file.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            }
        ]
        result = mcp_to_anthropic_tools(mcp_tools)
        assert len(result) == 1
        tool = result[0]
        assert tool["name"] == "read_file"
        assert tool["description"] == "Read a file."
        # Key conversion: inputSchema → input_schema
        assert "input_schema" in tool
        assert "inputSchema" not in tool
        assert tool["input_schema"]["type"] == "object"

    def test_multiple_tools(self) -> None:
        mcp_tools = [
            {"name": "a", "description": "A", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "b", "description": "B", "inputSchema": {"type": "object", "properties": {}}},
        ]
        result = mcp_to_anthropic_tools(mcp_tools)
        assert len(result) == 2
        assert result[0]["name"] == "a"
        assert result[1]["name"] == "b"

    def test_empty_list(self) -> None:
        assert mcp_to_anthropic_tools([]) == []


class TestSerializeContent:
    def test_dict_passthrough(self) -> None:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": "hello"}]
        assert serialize_content(blocks) == [{"type": "text", "text": "hello"}]

    def test_pydantic_model_dump(self) -> None:
        mock = MagicMock()
        mock.model_dump.return_value = {"type": "text", "text": "from model"}
        result = serialize_content([mock])
        assert result == [{"type": "text", "text": "from model"}]
        mock.model_dump.assert_called_once()

    def test_fallback_to_str(self) -> None:
        result = serialize_content([42])
        assert result == [{"type": "text", "text": "42"}]
