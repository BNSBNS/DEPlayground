"""Scanner orchestrator — runs all testers against a target and returns a ScanResult."""

from __future__ import annotations

import contextlib
import datetime

import httpx

from src.config import ScannerSettings
from src.discovery.openapi_parser import fetch_openapi_spec
from src.models import ScanResult
from src.testers.auth_tester import AuthTester, FunctionAuthTester
from src.testers.bola_tester import BOLATester
from src.testers.business_flow_tester import BusinessFlowTester
from src.testers.consumption_tester import ConsumptionTester
from src.testers.injection_tester import InjectionTester
from src.testers.inventory_tester import InventoryTester
from src.testers.jwt_tester import JWTTester
from src.testers.misconfig_tester import MisconfigTester
from src.testers.rate_limit_tester import RateLimitTester
from src.testers.ssrf_tester import SSRFTester


async def _get_alice_token(client: httpx.AsyncClient, target: str) -> str:
    """Obtain a regular-user JWT from the target — used for BOLA and function-level tests."""
    with contextlib.suppress(Exception):
        resp = await client.post(
            f"{target}/api/v1/auth/login",
            json={"username": "alice", "password": "alice_password"},
        )
        if resp.status_code == 200:
            return str(resp.json().get("access_token", ""))
    return ""


async def run_scan(
    target_url: str,
    *,
    settings: ScannerSettings | None = None,
) -> ScanResult:
    """Run the full security test suite against *target_url* and return findings.

    Steps:
      1. Discover endpoints from OpenAPI spec
      2. Obtain a regular-user token (if the target supports it)
      3. Execute all testers — standalone + per-endpoint
      4. Seal the result and return
    """
    if settings is None:
        settings = ScannerSettings(target_url=target_url)

    result = ScanResult(target_url=target_url)

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        # ── Discovery ────────────────────────────────────────────────────────
        endpoints = await fetch_openapi_spec(target_url)

        # ── Obtain a regular-user token for auth-dependent tests ─────────────
        alice_token = await _get_alice_token(client, target_url)

        # ── Standalone testers ────────────────────────────────────────────────
        await JWTTester(client, target_url).run(result)
        await RateLimitTester(client, target_url).run(result)
        await BusinessFlowTester(client, target_url).run(result)
        await MisconfigTester(client, target_url).run(result)
        await InventoryTester(client, target_url).run(result)
        await ConsumptionTester(client, target_url).run(result)

        if alice_token:
            await FunctionAuthTester(client, target_url, user_token=alice_token).run(result)

        # ── Per-endpoint testers ──────────────────────────────────────────────
        auth_tester = AuthTester(client, target_url)
        injection_tester = InjectionTester(client, target_url)
        ssrf_tester = SSRFTester(client, target_url)
        inventory_per = InventoryTester(client, target_url)
        consumption_per = ConsumptionTester(client, target_url)

        bola_tester: BOLATester | None = None
        if alice_token:
            bola_tester = BOLATester(
                client,
                target_url,
                user_a_token=alice_token,
                user_b_ids=[2, 3, 4],
            )

        for endpoint in endpoints:
            await auth_tester.test_endpoint(endpoint, result)
            await injection_tester.test_endpoint(endpoint, result)
            await ssrf_tester.test_endpoint(endpoint, result)
            await inventory_per.test_endpoint(endpoint, result)
            await consumption_per.test_endpoint(endpoint, result)
            if bola_tester is not None:
                await bola_tester.test_endpoint(endpoint, result)

        result.completed_at = datetime.datetime.now(datetime.UTC)

    return result
