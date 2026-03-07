"""Endpoint mapper — derives test targets from a discovered endpoint list."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import Endpoint

# Regex to detect path parameters like {user_id} or :id
_PATH_PARAM_RE = re.compile(r"\{([^}]+)\}|:([a-zA-Z_][a-zA-Z0-9_]*)")


@dataclass
class EndpointMap:
    """Processed view of discovered endpoints, grouped by test relevance."""

    all_endpoints: list[Endpoint]
    # Endpoints with path parameters (BOLA candidates)
    parameterised: list[Endpoint] = field(default_factory=list)
    # Endpoints with no auth requirement (auth bypass candidates)
    unauthenticated: list[Endpoint] = field(default_factory=list)
    # POST/PUT/PATCH endpoints (injection + mass assignment candidates)
    write_endpoints: list[Endpoint] = field(default_factory=list)
    # Admin-looking paths
    admin_endpoints: list[Endpoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        for ep in self.all_endpoints:
            if _PATH_PARAM_RE.search(ep.path):
                self.parameterised.append(ep)
            if not ep.requires_auth:
                self.unauthenticated.append(ep)
            if ep.method in ("POST", "PUT", "PATCH"):
                self.write_endpoints.append(ep)
            if _is_admin_path(ep.path):
                self.admin_endpoints.append(ep)


def _is_admin_path(path: str) -> bool:
    admin_keywords = ("admin", "internal", "management", "superuser", "root", "staff")
    return any(kw in path.lower() for kw in admin_keywords)


def build_endpoint_map(endpoints: list[Endpoint]) -> EndpointMap:
    """Build a categorised EndpointMap from a flat endpoint list."""
    return EndpointMap(all_endpoints=endpoints)


def extract_path_params(endpoint: Endpoint) -> list[str]:
    """Return path parameter names extracted from the path template."""
    matches = _PATH_PARAM_RE.findall(endpoint.path)
    return [m[0] or m[1] for m in matches]


def generate_test_urls(endpoint: Endpoint, sample_ids: list[str | int]) -> list[str]:
    """Substitute path parameters with sample IDs to create concrete test URLs."""
    urls: list[str] = []
    params = extract_path_params(endpoint)
    if not params:
        return [endpoint.path]
    for sample_id in sample_ids:
        url = endpoint.path
        for param in params:
            # Replace {param} and :param style
            url = re.sub(rf"\{{{param}\}}", str(sample_id), url)
            url = re.sub(rf":{param}\b", str(sample_id), url)
        urls.append(url)
    return urls
