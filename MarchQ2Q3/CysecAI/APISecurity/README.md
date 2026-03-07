# APISecurity — OWASP API Top 10 Scanner

A black-box API security testing framework that automatically discovers endpoints from OpenAPI specifications and tests against all 10 OWASP API Security Top 10:2023 vulnerabilities. Results are exposed via a FastAPI REST interface and visualised in a Streamlit dashboard.

> **CysecAI Tier 2** — Targets: API Security Engineer, AppSec Engineer, DevSecOps

## OWASP API Security Top 10:2023 — Full Coverage

| Category | Tester | What It Checks |
|---|---|---|
| API1:2023 BOLA | `BOLATester` | Accesses resources using IDs belonging to other users |
| API2:2023 Broken Auth | `AuthTester` | Missing/bypassable auth, expired token acceptance |
| API3:2023 Property Auth | `InjectionTester` | Mass-assignment, excessive field exposure |
| API4:2023 Consumption | `RateLimitTester` | 50-request burst — checks for 429/503 responses |
| API5:2023 Function Auth | `FunctionAuthTester` | Admin-only endpoints accessible to regular users |
| API6:2023 Business Flow | `BusinessFlowTester` | Mass bot account registration (10 accounts, ≥80% success = finding) |
| API7:2023 SSRF | `SSRFTester` | URL query parameters probed with internal-address payloads |
| API8:2023 Misconfig | `MisconfigTester` | CORS wildcard, missing security headers, verbose errors, debug endpoints |
| API9:2023 Inventory | `InventoryTester` | Shadow APIs, undocumented paths, legacy version endpoints |
| API10:2023 Unsafe Consumption | `ConsumptionTester` | Unbounded list responses, sensitive fields in aggregated data |
| — (bonus) | `InjectionTester` | SQL/NoSQL injection pattern detection |
| — (bonus) | `JWTTester` | JWT algorithm confusion (none, HS256→RS256) |

## Project Structure

```
APISecurity/
├── src/
│   ├── api/
│   │   ├── main.py                  # FastAPI app with lifespan, /api/v1/ prefix
│   │   └── routers/
│   │       ├── health.py            # GET /health
│   │       └── scans.py             # POST/GET /api/v1/scans, GET /sarif
│   ├── alerts/
│   │   └── emitter.py               # emit() — writes findings as JSON alerts to disk
│   ├── dashboard/
│   │   └── app.py                   # Streamlit dashboard
│   ├── discovery/
│   │   ├── endpoint_mapper.py       # Normalises raw spec entries → Endpoint models
│   │   └── openapi_parser.py        # OpenAPI 3.0 spec fetcher + parser
│   ├── reports/
│   │   ├── json_report.py           # generate_json_report(), write_json_report()
│   │   └── sarif.py                 # generate_sarif(), write_sarif() (SARIF 2.1.0)
│   ├── testers/
│   │   ├── base.py                  # BaseTester ABC
│   │   ├── auth_tester.py           # API2 + API3
│   │   ├── bola_tester.py           # API1
│   │   ├── business_flow_tester.py  # API6
│   │   ├── consumption_tester.py    # API10
│   │   ├── injection_tester.py      # API3 (mass-assignment) + SQL injection
│   │   ├── inventory_tester.py      # API9
│   │   ├── jwt_tester.py            # API2 (JWT-specific)
│   │   ├── misconfig_tester.py      # API8
│   │   ├── rate_limit_tester.py     # API4
│   │   └── ssrf_tester.py           # API7
│   ├── vulnerable_app/
│   │   ├── main.py                  # Intentionally vulnerable FastAPI target
│   │   └── models.py
│   ├── config.py                    # ScannerSettings (Pydantic BaseSettings)
│   ├── models.py                    # Finding, Endpoint, ScanResult, enums
│   └── scanner.py                   # run_scan() orchestrator
├── tests/
│   └── unit/                        # 214 tests, 93%+ coverage
├── pyproject.toml
└── Makefile
```

## Quick Start

### Prerequisites

Conda environment `cysec` (Python 3.13):

```bash
conda activate cysec
cd MarchQ2Q3/CysecAI/APISecurity
make setup
```

### Start the Vulnerable Target API

The included vulnerable API provides a realistic test target:

```bash
uvicorn src.vulnerable_app.main:app --port 8001
```

### Run a Scan via Python

```python
import asyncio
from src.scanner import run_scan

result = asyncio.run(run_scan("http://localhost:8001"))
print(f"Found {result.finding_count} issues "
      f"({result.critical_count} critical, {result.high_count} high)")

for finding in result.findings:
    print(f"  [{finding.severity}] {finding.owasp_category}")
    print(f"    {finding.title} — {finding.endpoint}")
    print(f"    Evidence: {finding.evidence}")
```

### Start the Scanner API

```bash
uvicorn src.api.main:app --port 8002
```

### Start the Dashboard

```bash
streamlit run src/dashboard/app.py
```

## REST API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — `{"status": "ok", "service": "APISecurity Scanner API"}` |
| `POST` | `/api/v1/scans` | Submit scan. Body: `{"target_url": "...", "timeout": 10.0}`. Returns 202 + `scan_id`. |
| `GET` | `/api/v1/scans` | List all submitted scans with status |
| `GET` | `/api/v1/scans/{id}` | Full JSON report (pending/running scans return status only) |
| `GET` | `/api/v1/scans/{id}/sarif` | SARIF 2.1.0 report (409 if scan not complete) |

### Example: Submit and Poll

```bash
# Submit
SCAN=$(curl -s -X POST http://localhost:8002/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target_url": "http://localhost:8001"}')
SCAN_ID=$(echo $SCAN | python -c "import sys,json; print(json.load(sys.stdin)['scan_id'])")

# Poll until complete
curl http://localhost:8002/api/v1/scans/$SCAN_ID

# Download SARIF
curl http://localhost:8002/api/v1/scans/$SCAN_ID/sarif > results.sarif
```

## Report Formats

### JSON Report

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "target_url": "http://localhost:8001",
  "started_at": "2026-01-01T00:00:00+00:00",
  "completed_at": "2026-01-01T00:01:03+00:00",
  "endpoints_scanned": 12,
  "finding_count": 7,
  "critical_count": 1,
  "high_count": 2,
  "findings": [
    {
      "finding_id": "...",
      "owasp_category": "API1:2023 Broken Object Level Authorization",
      "title": "BOLA: Accessed another user's resource",
      "severity": "CRITICAL",
      "endpoint": "/api/v1/users/2/orders",
      "method": "GET",
      "evidence": "HTTP 200 — accessed user 2 resources as user 1",
      "remediation": "Enforce object-level authorisation on every endpoint.",
      "timestamp": "2026-01-01T00:00:10+00:00"
    }
  ]
}
```

### SARIF 2.1.0

Compatible with GitHub Code Scanning for PR-integrated security reports:

```bash
# Upload to GitHub Code Scanning
gh api repos/{owner}/{repo}/code-scanning/sarifs \
  -f commit_sha=$(git rev-parse HEAD) \
  -f ref=refs/heads/main \
  -f sarif=$(cat results.sarif | gzip | base64)
```

Severity mapping: `CRITICAL/HIGH → error`, `MEDIUM → warning`, `LOW/INFO → note`

## Scanner Architecture

```
run_scan(target_url)
   │
   ├── fetch_openapi_spec()          # GET /openapi.json → list[Endpoint]
   ├── _get_alice_token()            # POST /api/v1/auth/login → JWT token
   │
   ├── Standalone testers (run once per scan)
   │   ├── JWTTester                 # JWT algorithm confusion
   │   ├── RateLimitTester           # 50 concurrent requests to auth endpoints
   │   ├── BusinessFlowTester        # 10 bot account registrations
   │   ├── MisconfigTester           # CORS/headers/debug/verbose errors
   │   ├── InventoryTester           # 14 common shadow/undocumented paths
   │   ├── ConsumptionTester         # Unbounded responses, sensitive fields
   │   └── FunctionAuthTester        # Admin endpoint access (token required)
   │
   └── Per-endpoint testers (run for each discovered endpoint)
       ├── AuthTester                # Missing auth, expired token
       ├── InjectionTester           # SQL injection payloads, mass assignment
       ├── SSRFTester                # Internal URL payloads in URL params
       ├── InventoryTester           # Legacy version variants (/v0/, /v1/)
       ├── ConsumptionTester         # Response body field analysis
       └── BOLATester                # Cross-user ID access (token required)
```

BOLA and FunctionAuth testers are skipped when login fails — no false positives from unauthenticated scans.

## Vulnerable Test Target

`src/vulnerable_app/main.py` is a deliberately insecure FastAPI application for scanner validation:

| Vulnerability | Endpoint | OWASP Category |
|---|---|---|
| BOLA — any user's orders accessible | `GET /api/v1/users/{id}/orders` | API1 |
| Unauthenticated admin endpoint | `GET /api/v1/admin/users` | API2, API5 |
| JWT `none` algorithm accepted | `POST /api/v1/auth/verify` | API2 |
| Mass assignment — role field accepted | `PUT /api/v1/users/{id}` | API3 |
| No rate limiting | All endpoints | API4 |
| Mass registration — no automation block | `POST /api/v1/auth/register` | API6 |
| CORS wildcard | All responses | API8 |
| Missing security headers | All responses | API8 |
| Debug endpoint exposed | `GET /debug/config` | API8 |
| Stack traces in 500 responses | Error responses | API8 |

## Configuration

Settings via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_URL` | `http://localhost:8001` | API base URL to scan |
| `REQUEST_TIMEOUT` | `10.0` | Per-request timeout in seconds |
| `BURST_COUNT` | `50` | Concurrent requests for rate-limit testing (API4) |
| `REGISTRATION_COUNT` | `10` | Bot accounts for business-flow testing (API6) |

## Core Models

```python
class Finding(BaseModel):
    finding_id: str          # UUID, auto-generated
    owasp_category: OWASPCategory
    title: str
    severity: Severity       # CRITICAL | HIGH | MEDIUM | LOW | INFO
    endpoint: str
    method: str              # HTTP method
    evidence: str            # What the tester observed
    remediation: str         # How to fix it
    timestamp: datetime

class ScanResult(BaseModel):
    scan_id: str
    target_url: str
    findings: list[Finding]
    endpoints_scanned: int
    started_at: datetime
    completed_at: datetime | None

    # Computed properties
    finding_count: int
    critical_count: int
    high_count: int
```

## Development

```bash
make setup        # pip install -e ".[dev]"
make lint         # ruff check src/ tests/
make format       # ruff format src/ tests/
make type-check   # mypy src/ --strict
make test         # pytest tests/ -q (coverage report included)
make test-cov     # pytest with HTML coverage report
```

## Test Suite

```
tests/unit/
├── test_api.py               # FastAPI endpoints + scanner orchestrator
├── test_models.py            # Finding, ScanResult, enums
├── test_discovery.py         # OpenAPI parser + endpoint mapper
├── test_phase3_testers.py    # BOLA, Auth, FunctionAuth
├── test_phase4_testers.py    # Injection, JWT
├── test_phase5_testers.py    # RateLimit, BusinessFlow, SSRF, Misconfig
├── test_phase6.py            # Inventory, Consumption, alerts, reports
└── test_vulnerable_app.py    # Vulnerable target API (verifies vulns exist)
```

**214 tests · 93%+ coverage · zero mypy errors · zero ruff errors**

## Limitations

- REST only — does not test GraphQL or gRPC APIs
- SSRF detection is heuristic (response time ≥2s or 200 + >50 bytes content) — no callback server
- Rate-limit testing targets auth endpoints; other endpoints may have different limits
- Business-flow testing is generic (account registration); custom flows require extending `BusinessFlowTester`
- Does not replace manual penetration testing or authenticated DAST tooling

## Ethical Use

This tool is designed for:
- Security testing of APIs you own or have explicit written permission to test
- CI/CD pipeline integration for your own projects
- Security training and education using the included vulnerable test API

Do not use against APIs without authorisation.
