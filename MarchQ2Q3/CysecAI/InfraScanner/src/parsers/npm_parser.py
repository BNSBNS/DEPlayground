"""Parse Node.js dependency manifests: package.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.models import Dependency, Ecosystem

# Strip npm semver range prefix characters: ^, ~, >=, <=, >, <, =, *
_VERSION_PREFIX_RE = re.compile(r"^[^0-9]*")


def _extract_version(spec: str) -> tuple[str | None, str | None]:
    """Split an npm version spec into (version, constraint).

    Returns (version, None) for exact pins, (None, constraint) for ranges.
    """
    spec = spec.strip()
    if not spec or spec in {"*", "latest"}:
        return None, None
    # Exact version: "1.2.3" or "v1.2.3"
    clean = spec.lstrip("v")
    if re.match(r"^\d+\.\d+", clean):
        return clean, None
    # Range operator: "^1.2.3", "~1.2.3", ">=1.2"
    return None, spec


def parse_package_json(
    content: str, source_file: str = "package.json", *, include_dev: bool = False
) -> list[Dependency]:
    """Parse package.json into Dependency objects."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    deps: list[Dependency] = []

    def _add(section: dict[str, object]) -> None:
        for name, spec in section.items():
            if not isinstance(spec, str):
                continue
            version, constraint = _extract_version(spec)
            deps.append(
                Dependency(
                    name=name,
                    version=version,
                    constraint=constraint,
                    ecosystem=Ecosystem.NPM,
                    source_file=source_file,
                )
            )

    if isinstance(data.get("dependencies"), dict):
        _add(data["dependencies"])
    if include_dev and isinstance(data.get("devDependencies"), dict):
        _add(data["devDependencies"])
    if isinstance(data.get("peerDependencies"), dict):
        _add(data["peerDependencies"])

    return deps


def parse_npm_file(path: Path, *, include_dev: bool = False) -> list[Dependency]:
    content = path.read_text(encoding="utf-8")
    return parse_package_json(content, source_file=str(path), include_dev=include_dev)
