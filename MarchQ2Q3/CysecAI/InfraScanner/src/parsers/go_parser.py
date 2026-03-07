"""Parse Go module manifests: go.mod."""

from __future__ import annotations

import re
from pathlib import Path

from src.models import Dependency, Ecosystem

# Matches: github.com/foo/bar v1.2.3 or github.com/foo/bar v1.2.3 // indirect
_REQUIRE_RE = re.compile(r"^\s*([A-Za-z0-9][\w./\-]+)\s+(v[0-9][^\s]*)(?:\s*//.*)?$")


def parse_go_mod(content: str, source_file: str = "go.mod") -> list[Dependency]:
    """Parse go.mod require blocks into Dependency objects."""
    deps: list[Dependency] = []
    in_require_block = False

    for line in content.splitlines():
        stripped = line.strip()

        # Handle require (...) blocks
        if stripped.startswith("require ("):
            in_require_block = True
            continue
        if in_require_block and stripped == ")":
            in_require_block = False
            continue

        # Handle single-line: require github.com/foo/bar v1.2.3
        if stripped.startswith("require ") and "(" not in stripped:
            rest = stripped[len("require ") :].strip()
            m = _REQUIRE_RE.match(rest)
            if m:
                name = m.group(1)
                version = m.group(2).lstrip("v")
                deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem=Ecosystem.GO,
                        source_file=source_file,
                    )
                )
            continue

        if in_require_block:
            m = _REQUIRE_RE.match(stripped)
            if m:
                name = m.group(1)
                version = m.group(2).lstrip("v")
                deps.append(
                    Dependency(
                        name=name,
                        version=version,
                        ecosystem=Ecosystem.GO,
                        source_file=source_file,
                    )
                )

    return deps


def parse_go_file(path: Path) -> list[Dependency]:
    content = path.read_text(encoding="utf-8")
    return parse_go_mod(content, source_file=str(path))
