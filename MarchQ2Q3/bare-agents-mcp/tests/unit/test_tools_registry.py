"""Tests for the tool registry and tool implementations."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import src.tools.filesystem as fs_mod
import src.tools.notes as notes_mod
from src.tools import _REGISTRY, execute, get_all_definitions
from src.tools.filesystem import list_directory, read_file, write_file
from src.tools.notes import _notes, create_note, list_notes, search_notes


class TestToolRegistry:
    """Test the @register_tool decorator and registry functions."""

    def test_tools_are_registered(self) -> None:
        expected = {
            "read_file",
            "write_file",
            "list_directory",
            "create_note",
            "list_notes",
            "search_notes",
        }
        assert set(_REGISTRY.keys()) == expected

    def test_get_all_definitions_format(self) -> None:
        defs = get_all_definitions()
        assert isinstance(defs, list)
        assert len(defs) == len(_REGISTRY)
        for d in defs:
            assert "name" in d
            assert "description" in d
            assert "inputSchema" in d
            assert d["inputSchema"]["type"] == "object"

    def test_execute_known_tool(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(fs_mod, "SANDBOX_ROOT", Path(tmpdir).resolve()),
        ):
            fpath = str(Path(tmpdir) / "test.txt")
            Path(fpath).write_text("hello", encoding="utf-8")
            result, is_error = execute("read_file", {"path": fpath})
        assert result == "hello"
        assert is_error is False

    def test_execute_unknown_tool(self) -> None:
        result, is_error = execute("nonexistent_tool", {})
        assert "unknown tool" in result
        assert is_error is True

    def test_execute_tool_exception(self) -> None:
        result, is_error = execute("read_file", {"path": "/nonexistent/path/abc123"})
        assert "Error executing" in result
        assert is_error is True


class TestFilesystemTools:
    """Test filesystem tool implementations with sandbox validation."""

    def test_read_write_roundtrip(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(fs_mod, "SANDBOX_ROOT", Path(tmpdir).resolve()),
        ):
            path = str(Path(tmpdir) / "test.txt")
            result = write_file(path, "test content")
            assert "Wrote" in result
            assert read_file(path) == "test content"

    def test_write_creates_parents(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(fs_mod, "SANDBOX_ROOT", Path(tmpdir).resolve()),
        ):
            path = str(Path(tmpdir) / "a" / "b" / "file.txt")
            write_file(path, "nested")
            assert read_file(path) == "nested"

    def test_list_directory(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(fs_mod, "SANDBOX_ROOT", Path(tmpdir).resolve()),
        ):
            (Path(tmpdir) / "a.txt").touch()
            (Path(tmpdir) / "b.txt").touch()
            result = list_directory(tmpdir)
            entries = json.loads(result)
            assert sorted(entries) == ["a.txt", "b.txt"]

    def test_sandbox_rejects_escape(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(fs_mod, "SANDBOX_ROOT", Path(tmpdir).resolve()),
            pytest.raises(PermissionError, match="escapes sandbox"),
        ):
            read_file("/etc/passwd")

    def test_sandbox_rejects_prefix_sibling(self) -> None:
        """Reject paths in a sibling dir whose name shares the sandbox prefix.

        E.g. sandbox=/tmp/app must reject /tmp/app-evil/file even though
        '/tmp/app-evil/file'.startswith('/tmp/app') is True.
        """
        with tempfile.TemporaryDirectory() as parent:
            sandbox = Path(parent) / "app"
            sandbox.mkdir()
            evil = Path(parent) / "app-evil"
            evil.mkdir()
            (evil / "secret.txt").write_text("stolen", encoding="utf-8")

            with (
                patch.object(fs_mod, "SANDBOX_ROOT", sandbox.resolve()),
                pytest.raises(PermissionError, match="escapes sandbox"),
            ):
                read_file(str(evil / "secret.txt"))

    def test_read_file_size_limit(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(fs_mod, "SANDBOX_ROOT", Path(tmpdir).resolve()),
        ):
            path = str(Path(tmpdir) / "big.txt")
            Path(path).write_text("x" * 100, encoding="utf-8")
            with (
                patch.object(fs_mod, "MAX_FILE_SIZE", 50),
                pytest.raises(ValueError, match="File too large"),
            ):
                read_file(path)


class TestNotesTools:
    """Test in-memory notes tool implementations."""

    def setup_method(self) -> None:
        _notes.clear()
        notes_mod._next_id = 0

    def test_create_and_list(self) -> None:
        result = create_note("Title", "Content")
        assert "Created note #1" in result
        listed = json.loads(list_notes())
        assert len(listed) == 1
        assert listed[0]["title"] == "Title"

    def test_list_empty(self) -> None:
        result = json.loads(list_notes())
        assert result == []

    def test_search_found(self) -> None:
        create_note("Python Guide", "Learn Python basics")
        create_note("Rust Guide", "Learn Rust basics")
        result = json.loads(search_notes("python"))
        assert len(result) == 1
        assert result[0]["title"] == "Python Guide"

    def test_search_not_found(self) -> None:
        create_note("Python Guide", "Learn Python")
        result = json.loads(search_notes("javascript"))
        assert result == []
