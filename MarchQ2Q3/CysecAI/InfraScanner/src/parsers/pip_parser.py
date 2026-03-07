"""Parse Python dependency manifests: requirements.txt and pyproject.toml."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from src.models import Dependency, Ecosystem

# PEP 440 version specifier pattern: e.g. ==1.0, >=2.0,<3, ~=1.4
_VERSION_CONSTRAINT_RE = re.compile(
    r"^([A-Za-z0-9_.\-\[\]]+)\s*([><=!~^][><=!~^]?\s*[0-9][^,;#\s]*)?"
)

# Match a pinned version: name==x.y.z
_PINNED_RE = re.compile(r"^([A-Za-z0-9_.\-\[\]]+)==([0-9][^\s;#,]*)")


def _normalise_name(name: str) -> str:
    """PEP 503: normalize package names by replacing [-_.] with -."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements(content: str, source_file: str = "requirements.txt") -> list[Dependency]:
    """Parse a requirements.txt file into Dependency objects."""
    deps: list[Dependency] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        # Skip blanks, comments, options (-r, -c, -e, --...)
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Skip VCS / URL dependencies
        if "://" in line or line.startswith("git+"):
            continue

        # Remove inline comment
        line = line.split("#")[0].split(";")[0].strip()
        if not line:
            continue

        pinned = _PINNED_RE.match(line)
        if pinned:
            name = _normalise_name(pinned.group(1).split("[")[0])
            version = pinned.group(2)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    ecosystem=Ecosystem.PYPI,
                    source_file=source_file,
                )
            )
            continue

        m = _VERSION_CONSTRAINT_RE.match(line)
        if m:
            name = _normalise_name(m.group(1).split("[")[0])
            constraint = m.group(2).strip() if m.group(2) else None
            deps.append(
                Dependency(
                    name=name,
                    constraint=constraint,
                    ecosystem=Ecosystem.PYPI,
                    source_file=source_file,
                )
            )
    return deps


def parse_pyproject(content: str, source_file: str = "pyproject.toml") -> list[Dependency]:
    """Parse pyproject.toml [project.dependencies] into Dependency objects."""
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return []

    dep_strings: list[str] = []
    project = data.get("project", {})
    if isinstance(project, dict):
        raw_deps = project.get("dependencies", [])
        if isinstance(raw_deps, list):
            dep_strings = [str(d) for d in raw_deps]

    # Also check [tool.poetry.dependencies]
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        poetry = tool.get("poetry", {})
        if isinstance(poetry, dict):
            poetry_deps = poetry.get("dependencies", {})
            if isinstance(poetry_deps, dict):
                for pkg, spec in poetry_deps.items():
                    if isinstance(spec, str) and pkg.lower() != "python":
                        dep_strings.append(f"{pkg}>={spec.lstrip('^~')}")

    return parse_requirements("\n".join(dep_strings), source_file=source_file)


def parse_pip_file(path: Path) -> list[Dependency]:
    """Auto-detect and parse a pip manifest file by name."""
    name = path.name.lower()
    content = path.read_text(encoding="utf-8")
    if name == "pyproject.toml":
        return parse_pyproject(content, source_file=str(path))
    return parse_requirements(content, source_file=str(path))
