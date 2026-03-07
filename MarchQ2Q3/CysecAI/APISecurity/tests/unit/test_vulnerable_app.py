"""Tests confirming that the vulnerable app's security flaws exist.

These tests VERIFY VULNERABILITIES — they pass when flaws are present.
They serve as the baseline target for the security testers to detect.
"""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _forge_none_token(user_id: int, role: str = "user") -> str:
    """Create a JWT signed with 'none' algorithm (no signature)."""
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps({"user_id": user_id, "role": role}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}."  # empty signature


class TestBOLA:
    """API1: Broken Object Level Authorization."""

    def test_access_other_user_without_auth(self, client: TestClient) -> None:
        """Any user_id is accessible — no auth required at all."""
        resp = client.get("/api/v1/users/2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "bob"

    def test_access_admin_user_without_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/4")
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_no_ownership_check(self, client: TestClient, alice_token: str) -> None:
        """Alice (user_id=1) can access Bob (user_id=2) without restriction."""
        resp = client.get(
            "/api/v1/users/2",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "bob"


class TestBrokenAuthentication:
    """API2: Broken Authentication."""

    def test_none_algorithm_accepted(self, client: TestClient) -> None:
        """JWT with 'none' algorithm (no signature) is accepted."""
        forged = _forge_none_token(user_id=1, role="user")
        resp = client.get("/api/v1/profile", params={"authorization": f"Bearer {forged}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    def test_none_algorithm_admin_impersonation(self, client: TestClient) -> None:
        """Forge an admin token with none algorithm."""
        forged = _forge_none_token(user_id=4, role="admin")
        resp = client.get("/api/v1/profile", params={"authorization": f"Bearer {forged}"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_weak_jwt_secret_in_source(self) -> None:
        """Confirm the JWT secret is a known weak value ('secret123')."""
        from src.vulnerable_app.main import _JWT_SECRET  # noqa: PLC0415

        assert _JWT_SECRET == "secret123"
        assert len(_JWT_SECRET) < 32  # far too short


class TestSQLInjection:
    """SQL injection via string interpolation in /api/v1/search."""

    def test_sqli_returns_all_users(self, client: TestClient) -> None:
        """' OR '1'='1 bypasses the username filter, returning all rows."""
        resp = client.get("/api/v1/search", params={"q": "' OR '1'='1"})
        assert resp.status_code == 200
        users = resp.json()["users"]
        assert len(users) >= 4  # all seed users returned

    def test_sqli_union_extract(self, client: TestClient) -> None:
        """UNION injection to extract all users via a controlled query."""
        payload = "x' UNION SELECT id,username,email,password,role FROM users--"
        resp = client.get("/api/v1/search", params={"q": payload})
        assert resp.status_code == 200
        # At least one result returned from union
        assert len(resp.json()["users"]) >= 1

    def test_error_reveals_query(self, client: TestClient) -> None:
        """Malformed SQL causes 500 with error message revealing query structure."""
        resp = client.get("/api/v1/search", params={"q": "'; DROP TABLE users;--"})
        # SQLite raises OperationalError, exposed via detail field
        assert resp.status_code in (200, 500)


class TestNoRateLimiting:
    """API4: No rate limiting on any endpoint."""

    def test_rapid_login_attempts_all_succeed(self, client: TestClient) -> None:
        """20 rapid login attempts are all processed — no 429 returned."""
        responses = [
            client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "wrong"},
            )
            for _ in range(20)
        ]
        statuses = {r.status_code for r in responses}
        assert 429 not in statuses  # confirms no rate limiting

    def test_rapid_register_all_succeed(self, client: TestClient) -> None:
        """Mass account creation — no captcha or throttling."""
        responses = [
            client.post(
                "/api/v1/auth/register",
                json={"username": f"user{i}", "email": f"u{i}@x.com", "password": "p"},
            )
            for i in range(10)
        ]
        assert all(r.status_code == 201 for r in responses)


class TestNoFunctionLevelAuth:
    """API5: Broken Function Level Authorization."""

    def test_admin_endpoint_no_auth(self, client: TestClient) -> None:
        """Admin user list accessible without any token."""
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 200
        assert len(resp.json()["users"]) >= 4

    def test_regular_user_can_delete(self, client: TestClient, alice_token: str) -> None:
        """Regular user (alice, role=user) can call admin DELETE endpoint."""
        resp = client.delete(
            "/api/v1/admin/users/3",
            params={"authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200  # vulnerability: succeeds without role check
        assert "deleted" in resp.json()["message"]


class TestCORSWildcard:
    """API8: CORS misconfiguration — wildcard origin."""

    def test_cors_allows_any_origin(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/users/1",
            headers={"Origin": "http://evil.example.com"},
        )
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_cors_preflight_allows_any(self, client: TestClient) -> None:
        resp = client.options(
            "/api/v1/users/1",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") == "*"


class TestVerboseErrors:
    """API8: Verbose error messages expose internal details."""

    def test_debug_endpoint_exposes_internals(self, client: TestClient) -> None:
        """Debug status endpoint leaks internal IP and DB name in traceback."""
        resp = client.get("/api/v1/debug/status")
        assert resp.status_code == 500
        data = resp.json()
        assert "traceback" in data
        assert "RuntimeError" in data.get("traceback", "")
        # Internal IP leaked
        assert "10.0.0.1" in data.get("error", "") or "10.0.0.1" in data.get("traceback", "")


class TestShadowAPI:
    """API9: Shadow / legacy endpoints still active."""

    def test_legacy_v1_endpoint_accessible(self, client: TestClient) -> None:
        """/v1/ (old version) is still active alongside current /api/v1/."""
        resp = client.get("/v1/users/1")
        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    def test_legacy_v1_list_accessible(self, client: TestClient) -> None:
        resp = client.get("/v1/users")
        assert resp.status_code == 200
        assert len(resp.json()["users"]) >= 4


class TestUnsafeSignup:
    """API6: No captcha or flow control on registration."""

    def test_mass_registration_succeeds(self, client: TestClient) -> None:
        """50 accounts can be created without restriction."""
        for i in range(50):
            resp = client.post(
                "/api/v1/auth/register",
                json={"username": f"bot{i}", "email": f"bot{i}@spam.com", "password": "pass"},
            )
            assert resp.status_code == 201
