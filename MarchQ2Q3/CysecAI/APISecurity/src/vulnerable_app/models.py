"""Pydantic models for the deliberately vulnerable test API."""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class User(BaseModel):
    id: int
    username: str
    email: str
    role: str
