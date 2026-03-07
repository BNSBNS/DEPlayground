"""OpenAPI 3.0 spec parser — extracts endpoints, parameters, auth requirements."""

from __future__ import annotations

from typing import Any

import httpx
import yaml

from src.models import Endpoint

# Supported HTTP methods in OpenAPI
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def _parse_parameters(raw_params: list[dict[str, Any]]) -> list[str]:
    """Extract parameter names from an OpenAPI parameter list."""
    return [p["name"] for p in raw_params if isinstance(p, dict) and "name" in p]


def _requires_auth(operation: dict[str, Any], global_security: list[dict[str, Any]]) -> bool:
    """Determine if an operation requires authentication."""
    # Operation-level security overrides global; empty list means explicitly unsecured
    if "security" in operation:
        return bool(operation["security"])
    return bool(global_security)


def _parse_path(
    path: str,
    path_item: dict[str, Any],
    global_security: list[dict[str, Any]],
) -> list[Endpoint]:
    """Parse all operations for a single path item."""
    endpoints: list[Endpoint] = []
    for method, operation in path_item.items():
        if method not in _HTTP_METHODS:
            continue
        if not isinstance(operation, dict):
            continue
        raw_params: list[dict[str, Any]] = []
        # Path-level parameters shared across all methods
        if "parameters" in path_item and isinstance(path_item["parameters"], list):
            raw_params.extend(path_item["parameters"])
        # Operation-level parameters (may override path-level)
        if "parameters" in operation and isinstance(operation["parameters"], list):
            raw_params.extend(operation["parameters"])

        endpoints.append(
            Endpoint(
                path=path,
                method=method.upper(),
                parameters=_parse_parameters(raw_params),
                requires_auth=_requires_auth(operation, global_security),
                description=str(operation.get("summary", operation.get("description", ""))),
            )
        )
    return endpoints


def parse_openapi_dict(spec: dict[str, Any]) -> list[Endpoint]:
    """Parse an OpenAPI 3.0 spec dict into a list of Endpoint objects."""
    global_security: list[dict[str, Any]] = spec.get("security", [])
    paths: dict[str, Any] = spec.get("paths", {})
    endpoints: list[Endpoint] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        endpoints.extend(_parse_path(str(path), path_item, global_security))
    return endpoints


def parse_openapi_json(raw: str) -> list[Endpoint]:
    """Parse an OpenAPI spec from a JSON string."""
    import json  # noqa: PLC0415

    spec: dict[str, Any] = json.loads(raw)
    return parse_openapi_dict(spec)


def parse_openapi_yaml(raw: str) -> list[Endpoint]:
    """Parse an OpenAPI spec from a YAML string."""
    spec: dict[str, Any] = yaml.safe_load(raw)
    return parse_openapi_dict(spec)


async def fetch_openapi_spec(base_url: str, *, timeout: float = 10.0) -> list[Endpoint]:
    """Fetch the OpenAPI spec from a running API and parse it.

    Tries common spec paths: /openapi.json, /docs/openapi.json, /swagger.json.
    """
    spec_paths = ["/openapi.json", "/api-docs", "/swagger.json", "/docs/openapi.json"]
    async with httpx.AsyncClient(timeout=timeout) as client:
        for spec_path in spec_paths:
            url = base_url.rstrip("/") + spec_path
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    spec: dict[str, Any] = resp.json()
                    return parse_openapi_dict(spec)
            except (httpx.HTTPError, ValueError):
                continue
    return []
