# InfraScanner

A Python-based supply chain security scanner. Parses Python, Node.js, Go, and Dockerfile dependency manifests; matches against OSV.dev for CVE data; detects Docker misconfigurations, license risk, and typosquatting; generates CycloneDX SBOMs and SARIF/JSON/HTML reports.

## Features

| Category | Capability |
|----------|-----------|
| **Parsers** | pip requirements.txt · pyproject.toml · package.json · go.mod · Dockerfile |
| **Vulnerability DB** | OSV.dev batch API (PyPI, npm, Go) · CVSS + EPSS scoring |
| **Docker** | 7 CIS Benchmark checks (root, latest, privileged ports, HEALTHCHECK, ADD remote, secrets, sudo) |
| **License** | SPDX classification — COPYLEFT / RESTRICTED / ALLOWED / UNKNOWN |
| **Typosquatting** | Levenshtein distance ≤2 against top-50 PyPI + npm packages |
| **SBOM** | CycloneDX 1.4 JSON with package URLs (purl) |
| **Scoring** | CVSS × EPSS priority score + CISA KEV +0.3 bonus |
| **Reports** | JSON · SARIF 2.1.0 · HTML · SecurityAlert JSON (MITRE T1195.001) |
| **Interfaces** | CLI (Typer) · REST API (FastAPI) · Streamlit dashboard |

## Architecture

```
src/
  models.py                    # Dependency, Vulnerability, ScanFinding, ScanResult (Pydantic)
  config.py                    # InfraSettings (env-configurable)
  parsers/
    pip_parser.py              # requirements.txt + pyproject.toml (tomllib)
    npm_parser.py              # package.json (dependencies + peerDependencies)
    go_parser.py               # go.mod (require blocks + inline)
    dockerfile_parser.py       # FROM images + RUN pip/npm installs
  vuln_db/
    osv_client.py              # POST https://api.osv.dev/v1/querybatch
    nvd_client.py              # NVD REST API v2 (CVSS enrichment)
    matcher.py                 # Batch-queries OSV, returns ScanFindings
  scanners/
    docker_scanner.py          # CIS Docker Benchmark static analysis
    license_scanner.py         # SPDX license risk categorisation
    typosquat_detector.py      # Levenshtein distance against popular packages
    dependency_scanner.py      # Filesystem scanner (walk directory, auto-detect types)
  sbom/
    cyclonedx_generator.py     # CycloneDX 1.4 JSON SBOM
  scoring/
    prioritizer.py             # CVSS x EPSS risk score + KEV bonus
  alerts/
    emitter.py                 # SecurityAlert JSON (MITRE T1195.001)
  reporting/
    ci_output.py               # to_json() + to_sarif() for CI integration
    html_report.py             # Jinja2 HTML report
  api/
    main.py                    # FastAPI app
    routers/
      health.py                # GET /health
      scan.py                  # POST /api/v1/scan and /api/v1/scan/report
  cli.py                       # Typer CLI: scan, self-scan
  dashboard/app.py             # Streamlit dashboard
test_projects/                 # Fixtures with known-vulnerable dependencies
  python_vulnerable/           # requests==2.18.4, cryptography==2.0.0, Django==2.2.0
  node_vulnerable/             # lodash 4.17.11, express 4.17.1
  go_vulnerable/               # jwt-go v3.2.0, golang.org/x/net v0.1.0
  docker_vulnerable/           # ubuntu:latest, no USER, ENV secrets
  typosquat/                   # requsets, numpyy, fasapi
```

## Scanning Logic

### OSV Vulnerability Matching

Single batch POST to `https://api.osv.dev/v1/querybatch` — no API key required. Returns CVEs, GHSA IDs, CVSS scores, and affected version ranges. Prefers CVE alias over GHSA display ID.

**Risk score** = `max(CVSS/10 x EPSS)` across all vulnerabilities for a package. CISA KEV packages receive a +0.3 bonus (capped at 1.0).

**Severity from CVSS:**

| CVSS Range | Severity |
|------------|----------|
| >= 9.0 | CRITICAL |
| >= 7.0 | HIGH |
| >= 4.0 | MEDIUM |
| > 0 | LOW |
| 0 | NONE |

### Docker Security Checks (CIS Benchmark)

| Check ID | Description | Severity |
|----------|-------------|----------|
| DKR-001 | No USER instruction — runs as root | HIGH |
| DKR-002 | `FROM *:latest` tag — non-deterministic builds | MEDIUM |
| DKR-003 | Privileged port EXPOSE (< 1024) | LOW |
| DKR-004 | `ADD` with remote URL — prefer COPY | MEDIUM |
| DKR-005 | No HEALTHCHECK instruction | LOW |
| DKR-006 | Secret in ENV (PASSWORD/SECRET/TOKEN/KEY) | CRITICAL |
| DKR-007 | `sudo` in RUN instruction | MEDIUM |

### Typosquatting Detection

Levenshtein distance ≤2 against the top-50 most downloaded PyPI and npm packages. Packages that ARE in the popular list are skipped. Only the closest match per package is reported.

### License Risk

SPDX IDs classified into four categories:

| Risk | Examples |
|------|---------|
| COPYLEFT | GPL-2.0, GPL-3.0, AGPL-3.0, LGPL-*, MPL-2.0, EUPL |
| RESTRICTED | SSPL-1.0, BSL-1.1, Elastic-2.0, Commons-Clause |
| ALLOWED | MIT, Apache-2.0, BSD-2/3-Clause, ISC, Unlicense, CC0 |
| UNKNOWN | Unrecognised identifier |

## API Reference

```
GET  /health
POST /api/v1/scan          body: {"files": [...], "format": "json"}  -> 202
POST /api/v1/scan/report   body: {"files": [...], "format": "json"|"sarif"}
```

### File Types

| `file_type` | Description |
|-------------|-------------|
| `pip_requirements` | requirements.txt |
| `pyproject` | pyproject.toml (PEP 621 + Poetry) |
| `package_json` | package.json |
| `go_mod` | go.mod |
| `dockerfile` | Dockerfile |

### Example

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {"name": "requirements.txt", "content": "requests==2.18.4\n", "file_type": "pip_requirements"},
      {"name": "Dockerfile", "content": "FROM ubuntu:latest\nCMD bash\n", "file_type": "dockerfile"}
    ]
  }'
```

### Example Response

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "summary": {
    "total_dependencies": 1,
    "total_vulnerabilities": 3,
    "critical": 0,
    "high": 2,
    "findings": [
      {
        "package": "requests",
        "version": "2.18.4",
        "ecosystem": "pypi",
        "risk_score": 0.72,
        "vulnerabilities": [
          {"id": "CVE-2023-32681", "severity": "HIGH", "cvss": 7.2, "epss": 0.1}
        ]
      }
    ],
    "docker_findings": [
      {"check_id": "DKR-002", "severity": "MEDIUM", "description": "FROM ubuntu:latest — avoid 'latest'"},
      {"check_id": "DKR-005", "severity": "LOW",    "description": "No HEALTHCHECK instruction"},
      {"check_id": "DKR-001", "severity": "HIGH",   "description": "No USER — container runs as root"}
    ]
  }
}
```

## CLI

```bash
# Scan a project directory (auto-detects requirements.txt, package.json, go.mod, Dockerfile)
infrascan scan ./my-project

# Scan InfraScanner itself (dogfooding)
infrascan self-scan

# Output as SARIF for GitHub Code Scanning
infrascan scan ./my-project --format sarif --output results.sarif
```

## Streamlit Dashboard

```bash
streamlit run src/dashboard/app.py
```

Upload any supported manifest file. The dashboard displays:

- Metric cards: Total Dependencies / Vulnerabilities / Critical / High
- Vulnerability table sorted by Risk Score
- Docker security issues table
- Typosquatting warnings table
- SBOM download button (CycloneDX JSON)

## Configuration

All thresholds configurable via environment variables (`INFRA_` prefix):

| Variable | Default | Description |
|----------|---------|-------------|
| `INFRA_TYPOSQUAT_DISTANCE` | 2 | Max Levenshtein distance for typosquat detection |
| `INFRA_OSV_TIMEOUT_S` | 30 | OSV API timeout in seconds |
| `INFRA_NVD_API_KEY` | "" | Optional NVD API key (10x rate limit) |

## Development

```bash
# Install
pip install -e ".[dev]"

# Quality gate
make lint        # ruff check — zero errors
make format      # ruff format --check
make type-check  # mypy --strict — zero errors
make test-cov    # pytest — 89% coverage

# Run API
uvicorn src.api.main:app --reload

# Run dashboard
streamlit run src/dashboard/app.py
```

## Test Coverage

175 tests · 89% coverage

| Module | Coverage |
|--------|----------|
| `models.py` | 100% |
| `parsers/` | 86–94% |
| `vuln_db/matcher.py` | 100% |
| `vuln_db/osv_client.py` | 89% |
| `scanners/docker_scanner.py` | 96% |
| `scanners/typosquat_detector.py` | 100% |
| `sbom/` | 100% |
| `scoring/` | 100% |
| `reporting/` | 100% |
| `api/` | 85–100% |

## MITRE ATT&CK Coverage

| Technique | ID | Scanner |
|-----------|----|---------|
| Supply Chain Compromise: Software Dependencies | T1195.001 | OSV vulnerability matcher |
| Acquire Infrastructure: Domains | T1583.001 | Typosquat detector |
| Valid Accounts | T1078 | Docker root user check (DKR-001) |
| Credentials In Files | T1552.001 | Docker secret ENV check (DKR-006) |
