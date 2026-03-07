"""Tests for OpenAPI parser and endpoint mapper."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from src.discovery.endpoint_mapper import (
    EndpointMap,
    build_endpoint_map,
    extract_path_params,
    generate_test_urls,
)
from src.discovery.openapi_parser import (
    fetch_openapi_spec,
    parse_openapi_dict,
    parse_openapi_json,
    parse_openapi_yaml,
)
from src.models import Endpoint

# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_spec(
    *,
    with_auth: bool = True,
    include_admin: bool = False,
) -> dict:  # type: ignore[type-arg]
    """Build a minimal OpenAPI 3.0 spec dict."""
    paths: dict = {  # type: ignore[type-arg]
        "/api/v1/users": {
            "get": {
                "summary": "List users",
                "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                "security": [{"BearerAuth": []}] if with_auth else [],
            },
            "post": {
                "summary": "Create user",
                "security": [{"BearerAuth": []}] if with_auth else [],
            },
        },
        "/api/v1/users/{user_id}": {
            "parameters": [{"name": "user_id", "in": "path"}],
            "get": {"summary": "Get user"},
            "delete": {"summary": "Delete user"},
        },
        "/api/v1/search": {
            "get": {
                "summary": "Search",
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}],
                "security": [],  # explicitly unauthenticated
            },
        },
    }
    if include_admin:
        paths["/api/v1/admin/users"] = {
            "get": {"summary": "Admin list"},
        }
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0"},
        "security": [{"BearerAuth": []}] if with_auth else [],
        "paths": paths,
    }


# ── OpenAPI parser tests ─────────────────────────────────────────────────────


class TestParseOpenapiDict:
    def test_returns_endpoints(self) -> None:
        spec = _make_spec()
        endpoints = parse_openapi_dict(spec)
        assert len(endpoints) > 0

    def test_paths_extracted(self) -> None:
        spec = _make_spec()
        endpoints = parse_openapi_dict(spec)
        paths = {ep.path for ep in endpoints}
        assert "/api/v1/users" in paths
        assert "/api/v1/users/{user_id}" in paths

    def test_methods_extracted(self) -> None:
        spec = _make_spec()
        endpoints = parse_openapi_dict(spec)
        methods = {ep.method for ep in endpoints}
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods

    def test_path_parameter_in_endpoint(self) -> None:
        spec = _make_spec()
        endpoints = parse_openapi_dict(spec)
        user_detail = [ep for ep in endpoints if "{user_id}" in ep.path and ep.method == "GET"]
        assert len(user_detail) == 1
        assert "user_id" in user_detail[0].parameters

    def test_query_parameter_extracted(self) -> None:
        spec = _make_spec()
        endpoints = parse_openapi_dict(spec)
        list_ep = [ep for ep in endpoints if ep.path == "/api/v1/users" and ep.method == "GET"]
        assert len(list_ep) == 1
        assert "limit" in list_ep[0].parameters

    def test_auth_required_when_global_security(self) -> None:
        spec = _make_spec(with_auth=True)
        endpoints = parse_openapi_dict(spec)
        user_list = next(
            ep for ep in endpoints if ep.path == "/api/v1/users" and ep.method == "GET"
        )
        assert user_list.requires_auth is True

    def test_no_auth_when_operation_security_empty(self) -> None:
        """Operation with security: [] is explicitly unauthenticated."""
        spec = _make_spec(with_auth=True)
        endpoints = parse_openapi_dict(spec)
        search_ep = next(ep for ep in endpoints if ep.path == "/api/v1/search")
        assert search_ep.requires_auth is False

    def test_empty_paths(self) -> None:
        spec: dict = {"openapi": "3.0.0", "info": {}, "paths": {}}  # type: ignore[type-arg]
        assert parse_openapi_dict(spec) == []

    def test_description_extracted(self) -> None:
        spec = _make_spec()
        endpoints = parse_openapi_dict(spec)
        user_list = next(
            ep for ep in endpoints if ep.path == "/api/v1/users" and ep.method == "GET"
        )
        assert "List users" in user_list.description


class TestParseOpenapiJson:
    def test_parses_json_string(self) -> None:
        spec = _make_spec()
        json_str = json.dumps(spec)
        endpoints = parse_openapi_json(json_str)
        assert len(endpoints) > 0

    def test_same_result_as_dict(self) -> None:
        spec = _make_spec()
        from_dict = parse_openapi_dict(spec)
        from_json = parse_openapi_json(json.dumps(spec))
        assert len(from_dict) == len(from_json)


class TestParseOpenapiYaml:
    def test_parses_yaml_string(self) -> None:
        spec = _make_spec()
        yaml_str = yaml.dump(spec)
        endpoints = parse_openapi_yaml(yaml_str)
        assert len(endpoints) > 0


class TestFetchOpenapiSpec:
    @pytest.mark.asyncio
    async def test_fetches_from_openapi_json(self) -> None:
        spec = _make_spec()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value=spec)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            endpoints = await fetch_openapi_spec("http://localhost:8001")

        assert len(endpoints) > 0

    @pytest.mark.asyncio
    async def test_returns_empty_on_all_fail(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            endpoints = await fetch_openapi_spec("http://localhost:9999")

        assert endpoints == []

    @pytest.mark.asyncio
    async def test_skips_http_errors(self) -> None:
        import httpx as _httpx  # noqa: PLC0415

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=_httpx.ConnectError("refused"),
        ):
            endpoints = await fetch_openapi_spec("http://localhost:9999")

        assert endpoints == []


# ── Endpoint mapper tests ─────────────────────────────────────────────────────


class TestBuildEndpointMap:
    def _endpoints(self) -> list[Endpoint]:
        spec = _make_spec(include_admin=True)
        return parse_openapi_dict(spec)

    def test_parameterised_detected(self) -> None:
        em = build_endpoint_map(self._endpoints())
        paths = {ep.path for ep in em.parameterised}
        assert "/api/v1/users/{user_id}" in paths

    def test_unauthenticated_detected(self) -> None:
        em = build_endpoint_map(self._endpoints())
        paths = {ep.path for ep in em.unauthenticated}
        assert "/api/v1/search" in paths

    def test_write_endpoints_detected(self) -> None:
        em = build_endpoint_map(self._endpoints())
        methods = {ep.method for ep in em.write_endpoints}
        assert "POST" in methods

    def test_admin_endpoints_detected(self) -> None:
        em = build_endpoint_map(self._endpoints())
        paths = {ep.path for ep in em.admin_endpoints}
        assert "/api/v1/admin/users" in paths

    def test_all_endpoints_populated(self) -> None:
        endpoints = self._endpoints()
        em = build_endpoint_map(endpoints)
        assert len(em.all_endpoints) == len(endpoints)


class TestExtractPathParams:
    def test_curly_brace_syntax(self) -> None:
        ep = Endpoint(path="/api/v1/users/{user_id}/posts/{post_id}", method="GET")
        params = extract_path_params(ep)
        assert "user_id" in params
        assert "post_id" in params

    def test_colon_syntax(self) -> None:
        ep = Endpoint(path="/api/v1/users/:id", method="GET")
        params = extract_path_params(ep)
        assert "id" in params

    def test_no_params(self) -> None:
        ep = Endpoint(path="/api/v1/users", method="GET")
        assert extract_path_params(ep) == []


class TestGenerateTestUrls:
    def test_substitutes_ids(self) -> None:
        ep = Endpoint(path="/api/v1/users/{user_id}", method="GET")
        urls = generate_test_urls(ep, [1, 2, 3])
        assert "/api/v1/users/1" in urls
        assert "/api/v1/users/2" in urls
        assert "/api/v1/users/3" in urls

    def test_no_params_returns_path(self) -> None:
        ep = Endpoint(path="/api/v1/users", method="GET")
        urls = generate_test_urls(ep, [1, 2])
        assert urls == ["/api/v1/users"]

    def test_multiple_params(self) -> None:
        ep = Endpoint(path="/api/v1/users/{user_id}/posts/{post_id}", method="GET")
        urls = generate_test_urls(ep, [42])
        assert "/api/v1/users/42/posts/42" in urls


class TestEndpointMap:
    def test_empty_list(self) -> None:
        em = EndpointMap(all_endpoints=[])
        assert em.parameterised == []
        assert em.unauthenticated == []
        assert em.write_endpoints == []
        assert em.admin_endpoints == []
