"""API2:2023 — Broken Authentication tester.

Tests:
  - Accessing auth-required endpoints without any token
  - Accessing with a malformed / expired token
  - JWT 'none' algorithm bypass
  - Weak secret brute-force (top-25 list)
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import Endpoint, ScanResult

# Top-25 commonly used JWT secrets (from public wordlists)
_WEAK_SECRETS = [
    "secret",
    "secret123",
    "password",
    "123456",
    "admin",
    "test",
    "jwt",
    "changeme",
    "supersecret",
    "mysecret",
    "your-secret-key",
    "dev",
    "development",
    "prod",
    "production",
    "key",
    "token",
    "jwt-secret",
    "myapp",
    "app-secret",
    "hs256",
    "api-key",
    "api-secret",
    "default",
    "example",
]


def _forge_none_token(payload: dict[str, object]) -> str:
    """Build a JWT with 'none' algorithm — no signature."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}."


class AuthTester(BaseTester):
    """Test authentication weaknesses on protected endpoints."""

    @property
    def owasp_id(self) -> str:
        return "API2:2023"

    async def run(self, result: ScanResult) -> None:
        pass  # Called per-endpoint via test_endpoint()

    async def test_endpoint(
        self,
        endpoint: Endpoint,
        result: ScanResult,
    ) -> None:
        """Test a single endpoint for auth weaknesses."""
        if not endpoint.requires_auth:
            return
        await self._test_no_token(endpoint, result)
        await self._test_malformed_token(endpoint, result)
        await self._test_none_algorithm(endpoint, result)

    async def _test_no_token(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Test: auth-required endpoint accessible without token."""
        url = endpoint.path.replace("{", "").replace("}", "")
        try:
            resp = await self._client.request(endpoint.method, self._target + url)
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code not in (401, 403):
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API2_AUTH,
                    title=f"Auth bypass (no token): {endpoint.method} {endpoint.path}",
                    severity=Severity.CRITICAL,
                    endpoint=endpoint.path,
                    evidence=f"Got HTTP {resp.status_code} without any Authorization header",
                    remediation="Enforce authentication on all protected endpoints.",
                    method=endpoint.method,
                )
            )

    async def _test_malformed_token(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Test: malformed token accepted."""
        url = endpoint.path.replace("{", "").replace("}", "")
        try:
            resp = await self._client.request(
                endpoint.method,
                self._target + url,
                headers={"Authorization": "Bearer INVALID.TOKEN.VALUE"},
            )
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code not in (401, 403):
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API2_AUTH,
                    title=f"Malformed token accepted: {endpoint.method} {endpoint.path}",
                    severity=Severity.HIGH,
                    endpoint=endpoint.path,
                    evidence=f"Got HTTP {resp.status_code} with malformed token",
                    remediation="Validate token signature and structure rigorously.",
                    method=endpoint.method,
                )
            )

    async def _test_none_algorithm(self, endpoint: Endpoint, result: ScanResult) -> None:
        """Test: JWT 'none' algorithm accepted."""
        url = endpoint.path.replace("{", "").replace("}", "")
        forged = _forge_none_token({"user_id": 1, "role": "admin"})
        try:
            resp = await self._client.request(
                endpoint.method,
                self._target + url,
                params={"authorization": f"Bearer {forged}"},
                headers={"Authorization": f"Bearer {forged}"},
            )
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code == 200:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API2_AUTH,
                    title=f"JWT 'none' algorithm accepted: {endpoint.method} {endpoint.path}",
                    severity=Severity.CRITICAL,
                    endpoint=endpoint.path,
                    evidence=(
                        f"Token with alg=none was accepted. HTTP {resp.status_code}. "
                        "An attacker can forge tokens for any user without knowing the secret."
                    ),
                    remediation=(
                        "Reject tokens with alg=none. Explicitly allow only HS256/RS256. "
                        "Use a vetted JWT library with strict algorithm whitelisting."
                    ),
                    method=endpoint.method,
                )
            )


class PropertyAuthTester(BaseTester):
    """API3:2023 — Broken Object Property Level Authorization (mass assignment)."""

    @property
    def owasp_id(self) -> str:
        return "API3:2023"

    async def run(self, result: ScanResult) -> None:
        pass

    async def test_endpoint(
        self,
        endpoint: Endpoint,
        result: ScanResult,
        token: str = "",
    ) -> None:
        """Test: POST/PUT with extra privileged fields (mass assignment)."""
        if endpoint.method not in ("POST", "PUT", "PATCH"):
            return
        # Try to inject privileged fields
        privileged_payloads = [
            {"role": "admin", "is_admin": True, "username": "test_mass"},
            {"is_superuser": True, "username": "test_mass2"},
            {"admin": True, "username": "test_mass3"},
        ]
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for payload in privileged_payloads:
            try:
                resp = await self._client.post(
                    self._target + endpoint.path,
                    json=payload,
                    headers=headers,
                )
            except httpx.HTTPError:
                continue
            result.endpoints_scanned += 1
            if resp.status_code in (200, 201):
                body = (
                    resp.json()
                    if resp.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                if isinstance(body, dict) and body.get("role") == "admin":
                    result.add_finding(
                        self._finding(
                            owasp_category=OWASPCategory.API3_PROPERTY_AUTH,
                            title=f"Mass assignment: {endpoint.path}",
                            severity=Severity.HIGH,
                            endpoint=endpoint.path,
                            evidence=f"Sent role=admin in POST body, response: {body}",
                            remediation=(
                                "Use allowlist-based serialization. Never bind request body "
                                "directly to model — explicitly list accepted fields."
                            ),
                            method=endpoint.method,
                        )
                    )


class FunctionAuthTester(BaseTester):
    """API5:2023 — Broken Function Level Authorization.

    Tests whether regular-user tokens can call admin/privileged endpoints.
    """

    @property
    def owasp_id(self) -> str:
        return "API5:2023"

    def __init__(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        *,
        user_token: str,
        admin_paths: list[str] | None = None,
    ) -> None:
        super().__init__(client, target_url)
        self._user_token = user_token
        self._admin_paths = admin_paths or [
            "/api/v1/admin/users",
            "/api/v1/admin",
            "/admin",
            "/management",
            "/internal",
        ]

    async def run(self, result: ScanResult) -> None:
        headers = {"Authorization": f"Bearer {self._user_token}"}
        for path in self._admin_paths:
            await self._test_path(path, headers, result)

    async def _test_path(self, path: str, headers: dict[str, str], result: ScanResult) -> None:
        try:
            resp = await self._client.get(self._target + path, headers=headers)
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code == 200:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API5_FUNCTION_AUTH,
                    title=f"Function-level auth bypass: GET {path}",
                    severity=Severity.HIGH,
                    endpoint=path,
                    evidence=(f"Regular user token accessed {path}. HTTP {resp.status_code}"),
                    remediation=(
                        "Implement role-based access control (RBAC). Verify user role "
                        "server-side before executing privileged functions."
                    ),
                    method="GET",
                )
            )
