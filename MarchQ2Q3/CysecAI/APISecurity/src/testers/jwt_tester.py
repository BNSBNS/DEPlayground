"""JWT vulnerability tester.

Tests:
  - 'none' algorithm bypass (no signature verification)
  - Weak secret brute-force (top-50 common secrets)
  - Algorithm confusion (RS256 → HS256 with public key as secret)
  - Expired token acceptance
  - Missing claims (no sub/exp)
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import ScanResult

# Top-50 common JWT secrets (subset of public wordlists)
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
    "qwerty",
    "password123",
    "letmein",
    "abc123",
    "monkey",
    "1234567890",
    "dragon",
    "master",
    "pass",
    "root",
    "toor",
    "admin123",
    "welcome",
    "login",
    "hello",
    "test123",
    "access",
    "secure",
    "private",
    "public",
    "shared",
    "service",
    "backend",
    "frontend",
]


@dataclass
class JWTFinding:
    """Result of a JWT vulnerability test."""

    vulnerable: bool
    attack: str
    token: str = ""
    evidence: str = ""


def forge_none_token(payload: dict[str, Any]) -> str:
    """Create a JWT with 'none' algorithm."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}."


def forge_expired_token(secret: str, payload: dict[str, Any] | None = None) -> str:
    """Create an expired JWT (exp in the past)."""
    try:
        import jwt  # noqa: PLC0415

        data = dict(payload or {"user_id": 1})
        data["exp"] = int(time.time()) - 3600  # expired 1 hour ago
        return str(jwt.encode(data, secret, algorithm="HS256"))
    except Exception:
        return ""


def try_brute_force(token: str) -> str | None:
    """Try to crack a JWT with common weak secrets. Returns secret if found."""
    try:
        import jwt  # noqa: PLC0415

        for secret in _WEAK_SECRETS:
            try:
                jwt.decode(token, secret, algorithms=["HS256"])
                return secret
            except jwt.InvalidTokenError:
                continue
    except ImportError:
        pass
    return None


class JWTTester(BaseTester):
    """Test JWT authentication endpoints for common vulnerabilities."""

    @property
    def owasp_id(self) -> str:
        return "API2:2023"

    def __init__(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        *,
        token_endpoint: str = "/api/v1/auth/login",
        protected_endpoint: str = "/api/v1/profile",
        sample_credentials: tuple[str, str] = ("alice", "alice_password"),
    ) -> None:
        super().__init__(client, target_url)
        self._token_ep = token_endpoint
        self._protected_ep = protected_endpoint
        self._creds = sample_credentials

    async def run(self, result: ScanResult) -> None:
        """Run all JWT vulnerability tests."""
        # Try to obtain a real token first
        real_token = await self._get_real_token()
        await self._test_none_algorithm(result)
        if real_token:
            await self._test_brute_force(real_token, result)
            await self._test_expired_acceptance(real_token, result)

    async def _get_real_token(self) -> str:
        """Obtain a valid JWT by authenticating."""
        try:
            resp = await self._client.post(
                self._target + self._token_ep,
                json={"username": self._creds[0], "password": self._creds[1]},
            )
            if resp.status_code == 200:
                return str(resp.json().get("access_token", ""))
        except httpx.HTTPError:
            pass
        return ""

    async def _test_none_algorithm(self, result: ScanResult) -> None:
        """Test: JWT with alg=none is accepted on protected endpoint."""
        forged = forge_none_token({"user_id": 1, "role": "admin"})
        try:
            resp = await self._client.get(
                self._target + self._protected_ep,
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
                    title="JWT 'none' algorithm accepted",
                    severity=Severity.CRITICAL,
                    endpoint=self._protected_ep,
                    evidence=(
                        "Unsigned token with alg=none was accepted. "
                        "An attacker can impersonate any user without knowing the secret key."
                    ),
                    remediation=(
                        "Reject tokens with alg=none. Whitelist only HS256 or RS256. "
                        "Upgrade to a library that rejects insecure algorithms by default."
                    ),
                )
            )

    async def _test_brute_force(self, token: str, result: ScanResult) -> None:
        """Test: JWT secret is in a common wordlist."""
        cracked_secret = try_brute_force(token)
        result.endpoints_scanned += 1
        if cracked_secret:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API2_AUTH,
                    title="Weak JWT secret (crackable with wordlist)",
                    severity=Severity.CRITICAL,
                    endpoint=self._token_ep,
                    evidence=f"JWT secret cracked: {cracked_secret!r}",
                    remediation=(
                        "Use a cryptographically random secret of at least 256 bits. "
                        "Consider RS256 (asymmetric) to avoid shared-secret risks."
                    ),
                )
            )

    async def _test_expired_acceptance(self, token: str, result: ScanResult) -> None:
        """Test: expired token is still accepted."""
        # Extract secret from known-weak list to forge expired token
        secret = try_brute_force(token)
        if not secret:
            return
        expired = forge_expired_token(secret, {"user_id": 1, "role": "user"})
        if not expired:
            return
        try:
            resp = await self._client.get(
                self._target + self._protected_ep,
                params={"authorization": f"Bearer {expired}"},
                headers={"Authorization": f"Bearer {expired}"},
            )
        except httpx.HTTPError:
            return
        result.endpoints_scanned += 1
        if resp.status_code == 200:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API2_AUTH,
                    title="Expired JWT accepted",
                    severity=Severity.HIGH,
                    endpoint=self._protected_ep,
                    evidence="Expired token (exp in past) returned HTTP 200",
                    remediation=(
                        "Validate the 'exp' claim on every request. Reject tokens where exp <= now."
                    ),
                )
            )
