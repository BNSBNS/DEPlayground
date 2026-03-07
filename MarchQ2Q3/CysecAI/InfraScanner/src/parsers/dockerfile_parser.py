"""Parse Dockerfile for dependency and base image extraction."""

from __future__ import annotations

import re
from pathlib import Path

from src.models import Dependency, Ecosystem

# FROM image:tag or FROM image:tag AS stage
_FROM_RE = re.compile(r"^FROM\s+([^\s]+)(?:\s+AS\s+\S+)?", re.IGNORECASE)
# RUN pip install / pip3 install ...
_PIP_INSTALL_RE = re.compile(r"pip3?\s+install\s+(.+)", re.IGNORECASE)
# RUN npm install package or npm add package
_NPM_INSTALL_RE = re.compile(r"npm\s+(?:install|add|i)\s+([^-\s][^\s]*)", re.IGNORECASE)


def parse_dockerfile(content: str, source_file: str = "Dockerfile") -> list[Dependency]:
    """Extract base images and installed packages from a Dockerfile."""
    deps: list[Dependency] = []

    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Remove inline comments
        line = re.sub(r"\s*#.*$", "", line).strip()

        # FROM directives → docker ecosystem
        m = _FROM_RE.match(line)
        if m:
            image_ref = m.group(1)
            # name:tag format
            if ":" in image_ref:
                name, version = image_ref.rsplit(":", 1)
            else:
                name, version = image_ref, None
            # Skip ARG substitutions
            if "$" not in name:
                deps.append(
                    Dependency(
                        name=name,
                        version=version or None,
                        ecosystem=Ecosystem.DOCKER,
                        source_file=f"{source_file}:{lineno}",
                    )
                )
            continue

        # RUN pip install → pypi deps
        pm = _PIP_INSTALL_RE.search(line)
        if pm:
            for pkg_spec in pm.group(1).split():
                if pkg_spec.startswith("-"):
                    continue
                pkg_name = re.split(r"[>=<!\[\]]", pkg_spec)[0]
                if pkg_name:
                    deps.append(
                        Dependency(
                            name=pkg_name.lower(),
                            ecosystem=Ecosystem.PYPI,
                            source_file=f"{source_file}:{lineno}",
                        )
                    )
            continue

        # RUN npm install → npm deps
        nm = _NPM_INSTALL_RE.search(line)
        if nm:
            pkg = nm.group(1).strip()
            if pkg and not pkg.startswith("--"):
                deps.append(
                    Dependency(
                        name=pkg,
                        ecosystem=Ecosystem.NPM,
                        source_file=f"{source_file}:{lineno}",
                    )
                )

    return deps


def parse_dockerfile_file(path: Path) -> list[Dependency]:
    content = path.read_text(encoding="utf-8")
    return parse_dockerfile(content, source_file=str(path))
