"""Tests for Go module parser."""

from __future__ import annotations

from src.models import Ecosystem
from src.parsers.go_parser import parse_go_mod


class TestParseGoMod:
    _SAMPLE = """
module github.com/example/app

go 1.20

require (
    github.com/gin-gonic/gin v1.9.0
    golang.org/x/net v0.14.0
    github.com/stretchr/testify v1.8.4 // indirect
)

require github.com/some/pkg v2.1.0
"""

    def test_multi_require_block(self) -> None:
        deps = parse_go_mod(self._SAMPLE)
        names = [d.name for d in deps]
        assert "github.com/gin-gonic/gin" in names
        assert "golang.org/x/net" in names

    def test_version_stripped_of_v_prefix(self) -> None:
        deps = parse_go_mod(self._SAMPLE)
        gin = next(d for d in deps if d.name == "github.com/gin-gonic/gin")
        assert gin.version == "1.9.0"

    def test_indirect_deps_included(self) -> None:
        deps = parse_go_mod(self._SAMPLE)
        names = [d.name for d in deps]
        assert "github.com/stretchr/testify" in names

    def test_single_require_line(self) -> None:
        deps = parse_go_mod(self._SAMPLE)
        names = [d.name for d in deps]
        assert "github.com/some/pkg" in names

    def test_ecosystem_go(self) -> None:
        deps = parse_go_mod(self._SAMPLE)
        assert all(d.ecosystem == Ecosystem.GO for d in deps)

    def test_empty_mod(self) -> None:
        assert parse_go_mod("module myapp\n\ngo 1.20") == []

    def test_version_with_pseudo(self) -> None:
        content = "require github.com/foo/bar v0.0.0-20230101000000-abc123"
        deps = parse_go_mod(content)
        assert deps[0].version == "0.0.0-20230101000000-abc123"
