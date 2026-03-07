"""API6:2023 — Unrestricted Access to Sensitive Business Flows tester.

Detects: no bot protection, no CAPTCHA, no rate limiting on registration /
         account-creation flows that attackers can automate at scale.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import httpx

from src.models import OWASPCategory, Severity
from src.testers.base import BaseTester

if TYPE_CHECKING:
    from src.models import ScanResult

_REGISTRATION_COUNT = 10  # accounts to create in one burst
_SUCCESS_THRESHOLD = 0.8  # fraction of successes that triggers a finding


class BusinessFlowTester(BaseTester):
    """Detect unprotected automation-abusable flows (API6:2023)."""

    @property
    def owasp_id(self) -> str:
        return "API6:2023"

    async def run(self, result: ScanResult) -> None:
        await self._test_mass_registration(result)

    async def _test_mass_registration(self, result: ScanResult) -> None:
        tasks = [self._register_one(i) for i in range(_REGISTRATION_COUNT)]
        gathered: list[int | None] = list(await asyncio.gather(*tasks))

        valid = [r for r in gathered if r is not None]
        result.endpoints_scanned += len(valid)

        successes = [r for r in valid if r in (200, 201)]
        if valid and len(successes) >= len(valid) * _SUCCESS_THRESHOLD:
            result.add_finding(
                self._finding(
                    owasp_category=OWASPCategory.API6_BUSINESS_FLOW,
                    title="Unprotected mass account registration",
                    severity=Severity.HIGH,
                    endpoint="/api/v1/auth/register",
                    evidence=(
                        f"{len(successes)}/{_REGISTRATION_COUNT} automated registrations "
                        "succeeded without CAPTCHA or rate limiting."
                    ),
                    remediation=(
                        "Add CAPTCHA, email verification, and per-IP rate limiting to "
                        "registration endpoints. Monitor for bulk signup patterns."
                    ),
                    method="POST",
                )
            )

    async def _register_one(self, index: int) -> int | None:
        username = f"bot_user_{index}"
        with contextlib.suppress(httpx.HTTPError):
            resp = await self._client.post(
                self._target + "/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"{username}@bot.example.com",
                    "password": "botpassword123",
                },
            )
            return resp.status_code
        return None
