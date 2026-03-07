"""Deliberately vulnerable FastAPI application — FOR SECURITY TESTING ONLY.

WARNING: This application contains intentional security vulnerabilities:
  - API1:2023 BOLA (Broken Object Level Authorization)
  - API2:2023 Broken Authentication (none algorithm, weak JWT secret)
  - API4:2023 No rate limiting on any endpoint
  - API5:2023 No function-level authorization
  - API6:2023 Unprotected signup flow (no captcha)
  - API7:2023 Unsafe external API calls (no timeout, no TLS verify)
  - API8:2023 CORS wildcard, verbose errors with stack traces
  - API9:2023 Shadow legacy API endpoint (/v1/)
  - SQL injection via string interpolation in /api/v1/search

DO NOT deploy this outside a testing environment.
"""

from __future__ import annotations

import base64
import json
import sqlite3
import traceback
from typing import Any

import jwt
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.vulnerable_app.models import LoginRequest, RegisterRequest  # noqa: TC001

# ── Constants (intentionally weak) ──────────────────────────────────────────

_JWT_SECRET = "secret123"  # VULNERABILITY: weak secret present in common wordlists

# ── In-memory database ───────────────────────────────────────────────────────

_conn: sqlite3.Connection = sqlite3.connect(":memory:", check_same_thread=False)

_SEED_USERS = [
    (1, "alice", "alice@example.com", "alice_password", "user"),
    (2, "bob", "bob@example.com", "bob_password", "user"),
    (3, "charlie", "charlie@example.com", "charlie_password", "user"),
    (4, "admin", "admin@example.com", "admin_password", "admin"),
]


def _create_schema() -> None:
    _conn.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT, role TEXT)"
    )
    _conn.commit()


def reset_db_for_tests() -> None:
    """Reset database to initial seed state — for test isolation only."""
    _conn.execute("DELETE FROM users")
    _conn.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", _SEED_USERS)
    _conn.commit()


_create_schema()
reset_db_for_tests()


def _row_to_dict(row: tuple) -> dict[str, Any]:  # type: ignore[type-arg]
    return {"id": row[0], "username": row[1], "email": row[2], "role": row[4]}


# ── JWT helpers ──────────────────────────────────────────────────────────────


def _create_token(user_id: int, role: str) -> str:
    return jwt.encode({"user_id": user_id, "role": role}, _JWT_SECRET, algorithm="HS256")


def _decode_token_vulnerable(token: str) -> dict[str, Any]:
    """VULNERABILITY: accepts 'none' algorithm — no signature verification."""
    try:
        parts = token.split(".")
        padding = "=" * (4 - len(parts[0]) % 4)
        header_data = json.loads(base64.urlsafe_b64decode(parts[0] + padding))
        alg = header_data.get("alg", "HS256")
        if alg.lower() == "none":
            # VULNERABILITY: no signature check when alg=none
            payload_padding = "=" * (4 - len(parts[1]) % 4)
            payload_json = base64.urlsafe_b64decode(parts[1] + payload_padding)
            return dict(json.loads(payload_json))  # type: ignore[arg-type]
        result = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        return dict(result)  # type: ignore[arg-type]
    except (jwt.PyJWTError, json.JSONDecodeError, IndexError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Vulnerable API",
    description="Deliberately vulnerable FastAPI — FOR SECURITY TESTING ONLY.",
    version="2.0.0",
)

# VULNERABILITY: CORS wildcard — all origins, methods, headers allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# VULNERABILITY: verbose errors — full stack trace in response body
@app.exception_handler(Exception)
async def _verbose_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": traceback.format_exc()},
    )


# ── Auth routes ──────────────────────────────────────────────────────────────


@app.post("/api/v1/auth/login")
async def login(body: LoginRequest) -> dict[str, str]:
    row = _conn.execute(
        "SELECT id, username, email, password, role FROM users WHERE username = ?",
        (body.username,),
    ).fetchone()
    if not row or row[3] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": _create_token(row[0], row[4]), "token_type": "bearer"}


# VULNERABILITY API6: no captcha, no rate limit — automation / mass signup abuse
@app.post("/api/v1/auth/register", status_code=201)
async def register(body: RegisterRequest) -> dict[str, Any]:
    _conn.execute(
        "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, 'user')",
        (body.username, body.email, body.password),
    )
    _conn.commit()
    row = _conn.execute(
        "SELECT id, username, email, password, role FROM users WHERE username = ?",
        (body.username,),
    ).fetchone()
    return _row_to_dict(row)


# ── User routes ──────────────────────────────────────────────────────────────


# VULNERABILITY API1: BOLA — no authentication, any user_id is accessible
@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: int) -> dict[str, Any]:
    row = _conn.execute(
        "SELECT id, username, email, password, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_dict(row)


# VULNERABILITY: SQL injection via f-string query construction
@app.get("/api/v1/search")
async def search(q: str = Query(...)) -> dict[str, list[dict[str, Any]]]:
    # VULNERABILITY: raw string interpolation — SQLi attack possible
    query = f"SELECT id, username, email, password, role FROM users WHERE username LIKE '%{q}%'"
    try:
        rows = _conn.execute(query).fetchall()
    except sqlite3.OperationalError as exc:
        # VULNERABILITY: error message exposes query structure
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"users": [_row_to_dict(r) for r in rows]}


# VULNERABILITY API2: accepts JWT signed with 'none' algorithm
@app.get("/api/v1/profile")
async def profile(authorization: str = Query(default="")) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ")
    payload = _decode_token_vulnerable(token)
    row = _conn.execute(
        "SELECT id, username, email, password, role FROM users WHERE id = ?",
        (payload.get("user_id"),),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_dict(row)


# ── Admin routes — VULNERABILITY API5: no auth or role check ─────────────────


# VULNERABILITY: admin endpoint accessible without any token
@app.get("/api/v1/admin/users")
async def admin_list_users() -> dict[str, list[dict[str, Any]]]:
    rows = _conn.execute("SELECT id, username, email, password, role FROM users").fetchall()
    return {"users": [_row_to_dict(r) for r in rows]}


# VULNERABILITY API5: validates token but never checks role — regular users can delete
@app.delete("/api/v1/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    authorization: str = Query(default=""),
) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ")
    _decode_token_vulnerable(token)  # verifies token exists but not role
    _conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    _conn.commit()
    return {"message": f"User {user_id} deleted"}


# ── Shadow / legacy API — VULNERABILITY API9 ────────────────────────────────


# VULNERABILITY: old API version still active alongside v2
@app.get("/v1/users/{user_id}")
async def legacy_get_user(user_id: int) -> dict[str, Any]:
    return await get_user(user_id)


@app.get("/v1/users")
async def legacy_list_users() -> dict[str, list[dict[str, Any]]]:
    return await admin_list_users()


# ── Debug / verbose error demo ───────────────────────────────────────────────


# VULNERABILITY API8: debug endpoint left in production, leaks internals
@app.get("/api/v1/debug/status")
async def debug_status() -> dict[str, Any]:
    user_count = _conn.execute("SELECT count(*) FROM users").fetchone()[0]
    raise RuntimeError(f"Debug: {user_count} users in DB at 10.0.0.1:5432 (db=prod_users)")
