# DataSecurity

A Python-based database & data security toolkit. Discovers PII/PHI/PCI columns via regex and column-name heuristics, audits TDE and TLS encryption, masks or tokenizes sensitive values, logs queries to an append-only audit trail, and generates PDPA/GDPR/PCI-DSS compliance reports with HTML rendering.

## Features

| Category | Capability |
|----------|-----------|
| **PII Discovery** | Regex + column-name heuristics for email, phone, NRIC, SSN, credit card, IP, DOB, name, address |
| **Classification** | PII / PHI / PCI / PUBLIC with recommended masking strategy |
| **Schema Scanner** | SQLAlchemy `inspect()` — works across SQLite, PostgreSQL, MySQL |
| **Encryption Audit** | TDE check (TLS + DB-level) + TLS version / cipher detection |
| **Data Masking** | Email, phone, credit card, name, full-redact strategies |
| **Tokenization** | Format-preserving, Luhn-valid, HMAC-SHA256 deterministic PAN tokenization |
| **Key Management** | Key lifecycle tracking — rotation overdue detection, fingerprints |
| **Audit Logging** | Append-only SQLAlchemy-backed audit log with mutation guard |
| **Query Analysis** | Detects BULK_SELECT, SCHEMA_DUMP, PII_TABLE_WILDCARD, OFF_HOURS patterns |
| **Compliance** | PDPA (7 checks), GDPR (6 checks), PCI-DSS (6 checks) |
| **Reports** | JSON + Jinja2 HTML compliance reports |
| **Interfaces** | CLI (Typer) · REST API (FastAPI) · Streamlit dashboard |

## Architecture

```
src/
  models.py                    # DataClassification, PIIType, MaskingStrategy, EncryptionStatus, ...
  config.py                    # DataSecuritySettings (DS_ prefix env vars)
  db/
    adapter.py                 # AbstractDBAdapter (SQLAlchemy Inspector base)
    sqlite_adapter.py          # SQLite implementation
    postgres_adapter.py        # PostgreSQL TDE/TLS via pg_extension + SHOW ssl
    mysql_adapter.py           # MySQL TDE via INNODB_TABLESPACES FLAG
  discovery/
    pii_detector.py            # PIIDetector — regex + column-name heuristics, YAML-configurable
    classification.py          # classify_column() -> (DataClassification, MaskingStrategy)
    schema_scanner.py          # scan_schema() — iterate tables + classify all columns
  audit/
    tde_checker.py             # check_tde(adapter) -> EncryptionStatus
    tls_checker.py             # check_tls(adapter) -> EncryptionStatus; is_tls_secure()
    access_logger.py           # Append-only AccessLogger (SQLAlchemy ORM + before_flush guard)
    query_analyzer.py          # analyze_query() -> list[SuspiciousQueryType]
  protection/
    masking.py                 # mask_email/phone/credit_card/name/full_redact + apply_masking()
    tokenizer.py               # tokenize_credit_card() — format-preserving, Luhn-valid
    key_manager.py             # KeyManager + KeyRecord + fingerprint_key()
  compliance/
    pdpa_mapper.py             # map_pdpa() -> list[ComplianceRequirement]
    gdpr_mapper.py             # map_gdpr() -> list[ComplianceRequirement]
    pci_mapper.py              # map_pci() -> list[ComplianceRequirement]
    report_generator.py        # generate_report() -> ComplianceReport; render_html(), render_json()
  api/
    main.py                    # FastAPI app
    routers/
      health.py                # GET /health
      scan.py                  # POST /api/v1/scan and /api/v1/scan/pii
  cli.py                       # Typer CLI: scan, scan-pii
  dashboard/app.py             # Streamlit dashboard
config/
  pii_patterns.yaml            # Regex patterns for PII types
  masking_rules.yaml           # Masking strategy overrides per column
```

## PII Detection

Column names are matched against keyword lists for each `PIIType`. If no column-name match is found, the detector runs regex patterns against sample values.

| PIIType | Example Columns | Example Pattern |
|---------|----------------|----------------|
| `EMAIL` | `email`, `user_email` | `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}` |
| `PHONE` | `phone`, `mobile`, `tel` | `(\+?\d[\d\s\-()]{7,}\d)` |
| `CREDIT_CARD` | `credit_card`, `pan`, `card_number` | 16-digit groups |
| `NRIC` | `nric`, `national_id` | `[STFGM]\d{7}[A-Z]` |
| `SSN` | `ssn`, `social_security` | `\d{3}-\d{2}-\d{4}` |
| `IP_ADDRESS` | `ip`, `ip_address`, `source_ip` | IPv4 dotted-decimal |
| `DATE_OF_BIRTH` | `dob`, `birth_date`, `date_of_birth` | keyword heuristic |
| `NAME` | `full_name`, `first_name`, `last_name` | keyword heuristic |
| `ADDRESS` | `address`, `street`, `postal` | keyword heuristic |

## Data Classification

| Classification | Trigger | Default Masking Strategy |
|---------------|---------|------------------------|
| `PCI` | CREDIT_CARD PIIType | `CREDIT_CARD` |
| `PHI` | Diagnosis/medication/patient columns | `FULL_REDACT` |
| `PII` | Any other PII type | Varies by type |
| `PUBLIC` | No PII detected | `NONE` |

## Encryption Audit

### TDE (Transparent Data Encryption)

| Adapter | Check Method |
|---------|-------------|
| SQLite | Always disabled (SQLite does not support TDE) |
| PostgreSQL | `pg_tde` extension presence via `pg_extension` |
| MySQL | `INNODB_TABLESPACES` FLAG bitmask |

### TLS

| Adapter | Check Method |
|---------|-------------|
| SQLite | Always disabled (file-local, no network) |
| PostgreSQL | `SHOW ssl` + `pg_stat_ssl` for version/cipher |
| MySQL | `SHOW STATUS LIKE 'Ssl_%'` |

`is_tls_secure()` returns `True` only for TLSv1.2 or TLSv1.3.

## Data Masking

| Strategy | Input | Output |
|----------|-------|--------|
| `EMAIL` | `john.doe@example.com` | `j***@example.com` |
| `PHONE` | `+65-9123-4567` | `***-***-4567` |
| `CREDIT_CARD` | `4111 1111 1111 1234` | `****-****-****-1234` |
| `NAME` | `Jane Smith` | `J***` |
| `FULL_REDACT` | anything | `[REDACTED]` |

## Tokenization

Format-preserving credit card tokenization:
- Preserves 6-digit BIN and last-4 digits
- Luhn-valid output (passes credit card checksum)
- Deterministic via HMAC-SHA256 with a secret key
- One-way: `detokenize_credit_card()` raises `NotImplementedError`

## Compliance Reports

### PDPA (Personal Data Protection Act — Singapore)

| Requirement | ID | Check |
|-------------|-----|-------|
| Purpose Limitation | PDPA-1 | Manual review (N/A) |
| Notification Obligation | PDPA-2 | Manual review (N/A) |
| Consent Obligation | PDPA-3 | Manual review (N/A) |
| Access & Correction | PDPA-4 | Manual review (N/A) |
| Care Obligation (TLS) | PDPA-5 | TLS enabled check |
| Care Obligation (TDE) | PDPA-6 | TDE enabled check |
| Data Masking | PDPA-7 | PII columns present -> FAIL |

### GDPR

| Requirement | Article | Check |
|-------------|---------|-------|
| Integrity & Confidentiality | Art.5(1)(f) | TLS enabled |
| Privacy by Design | Art.25 | Pseudonymisation (masking) |
| Security of Processing | Art.32 | TDE + TLS |
| Data Minimisation | Art.5(1)(c) | Manual review (N/A) |
| Lawful Basis | Art.6 | Manual review (N/A) |
| Data Subject Rights | Art.17 | Manual review (N/A) |

### PCI-DSS

| Requirement | ID | Check |
|-------------|-----|-------|
| PAN storage | PCI-3.4 | Unprotected PAN columns + TDE |
| Encryption key protection | PCI-3.5 | Manual review (N/A) |
| TLS in transit | PCI-4.1 | TLS version check (rejects TLSv1.0/1.1) |
| Vulnerability management | PCI-6.3 | Manual review (N/A) |
| Access control | PCI-7.1 | Manual review (N/A) |
| Audit trail | PCI-10.2 | Manual review (N/A) |

## API Reference

```
GET  /health
POST /api/v1/scan          body: {"db_url": "sqlite:///...", "format": "json", "frameworks": ["pdpa"]}
POST /api/v1/scan/pii      body: {"db_url": "sqlite:///..."}
```

> **Security:** The `/api/v1/scan` endpoint only accepts `sqlite://` URLs to prevent SSRF against production databases.

### Example

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "db_url": "sqlite:///./tests/fixtures/test.db",
    "format": "json",
    "frameworks": ["pdpa", "gdpr", "pci"]
  }'
```

### Example Response

```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "summary": {
    "total_tables": 3,
    "pii_tables": 2,
    "pii_columns": 8,
    "frameworks_checked": ["pdpa", "gdpr", "pci"],
    "pass_count": 9,
    "fail_count": 5,
    "risk_score": 0.36
  },
  "compliance": [
    {
      "requirement_id": "PDPA-5",
      "framework": "PDPA",
      "article": "Care Obligation (TLS)",
      "status": "FAIL",
      "findings": ["TLS is not enabled on the database connection."],
      "remediation": "Enable TLS for all database connections."
    }
  ]
}
```

## CLI

```bash
# Scan a SQLite database, JSON output
datasec scan sqlite:///./my.db

# Scan with specific frameworks and HTML report
datasec scan sqlite:///./my.db --frameworks pdpa --format html --output report.html

# PII discovery only
datasec scan-pii sqlite:///./my.db
```

## Streamlit Dashboard

```bash
streamlit run src/dashboard/app.py
```

Enter a SQLite database URL and click **Scan**. The dashboard displays:

- Metric cards: Tables / PII Tables / PII Columns / Compliance Pass/Fail
- PII findings table sorted by classification
- Encryption status card (TDE + TLS)
- Compliance requirements table with status chips
- HTML report download button

## Configuration

All thresholds configurable via environment variables (`DS_` prefix):

| Variable | Default | Description |
|----------|---------|-------------|
| `DS_BULK_SELECT_THRESHOLD` | 10000 | Row count threshold for BULK_SELECT alert |
| `DS_OFF_HOURS_START` | 22 | Off-hours start (24h clock) |
| `DS_OFF_HOURS_END` | 6 | Off-hours end (24h clock) |
| `DS_DEFAULT_FRAMEWORKS` | pdpa,gdpr,pci | Compliance frameworks to check |

## Development

```bash
# Install
pip install -e ".[dev]"

# Quality gate
make lint        # ruff check — zero errors
make format      # ruff format --check
make type-check  # mypy --strict — zero errors
make test-cov    # pytest — 92% coverage

# Run API
uvicorn src.api.main:app --reload

# Run dashboard
streamlit run src/dashboard/app.py
```

## Test Coverage

166 tests · 92% coverage

| Module | Coverage |
|--------|----------|
| `models.py` | 100% |
| `db/adapter.py` | 100% |
| `db/sqlite_adapter.py` | 94% |
| `discovery/schema_scanner.py` | 100% |
| `discovery/classification.py` | 93% |
| `audit/tde_checker.py` | 100% |
| `audit/tls_checker.py` | 100% |
| `audit/access_logger.py` | 87% |
| `audit/query_analyzer.py` | 98% |
| `compliance/report_generator.py` | 100% |
| `compliance/gdpr_mapper.py` | 98% |
| `compliance/pdpa_mapper.py` | 97% |
| `compliance/pci_mapper.py` | 83% |
| `protection/masking.py` | 94% |
| `protection/tokenizer.py` | 98% |
| `protection/key_manager.py` | 98% |
| `api/` | 97-100% |

## MITRE ATT&CK Coverage

| Technique | ID | Scanner |
|-----------|----|---------|
| Credentials In Files | T1552.001 | PII detector — credit card + NRIC columns |
| Data from Local System | T1005 | Schema scanner — PII table discovery |
| Account Discovery | T1087 | Query analyzer — SCHEMA_DUMP detection |
| Exfiltration Over C2 Channel | T1041 | Query analyzer — BULK_SELECT + OFF_HOURS |
| Unsecured Credentials | T1552 | Encryption audit — TDE + TLS checks |
