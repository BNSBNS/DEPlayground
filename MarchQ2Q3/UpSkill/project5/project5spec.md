# Project 5: Data Contracts & Governance Platform

## What This Is
A platform where data producers declare contracts (schema, quality expectations, SLAs, ownership) and consumers subscribe to them. The system enforces contracts at pipeline runtime, detects violations, and provides a governance layer with audit trails, lineage, and ownership registry.

Producers promise "this table will have these columns, this freshness, this quality" — the system holds them accountable.

## Career Relevance
- **Data Engineering:** Data contracts is one of the hottest topics in modern data engineering (2024-2026) — building one is a strong differentiator
- **Platform Engineering:** This is governance infrastructure — the kind of system platform teams build to scale data orgs
- **ML Engineering:** ML models break silently when upstream data changes; contracts make schema/quality promises explicit and enforceable, preventing training-serving skew at the organizational level
- Shows "senior engineer" thinking: reliability, team coordination, and system-level data quality — not just individual pipeline correctness

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Contract store | PostgreSQL | Definitions, versions, violations, SLA records |
| Schema validation | JSON Schema | Structural validation of contract specs |
| Quality enforcement | Great Expectations + custom | Runtime quality checks |
| API | FastAPI | Contract CRUD, enforcement, webhooks |
| Frontend | Next.js | Contract catalog, violation dashboard, ownership map |
| Notifications | Slack (webhook) | Violation alerts to contract owners |
| Graph (optional) | Memgraph | Ownership graph, contract dependency visualization |
| CI integration | GitHub webhooks | Validate contracts on PR |

## Folder Structure

```
data-contracts/
├── docker-compose.yml          # app, postgres, frontend
├── pyproject.toml
├── .env.example
├── Makefile
├── README.md
├── src/
│   ├── config.py
│   ├── models/
│   ├── contracts/              # Parser, validator, version manager, differ
│   ├── schemas/                # JSON Schema registry, schema validator
│   ├── enforcement/            # Runtime checker, GE integration, webhook triggers
│   ├── governance/             # Ownership registry, audit logger, lineage linker
│   ├── notifications/          # Violation alerter, SLA breach notifier
│   ├── api/
│   └── db/
├── frontend/
│   ├── app/                    # Catalog, contract detail, violations, ownership
│   └── components/             # ContractCard, SchemaViewer, ViolationTimeline, OwnershipGraph
├── simulation/
│   ├── seed.py                 # Sample contracts, owners, teams, historical violations
│   ├── simulator.py            # Generate violations, SLA breaches
│   ├── sample_contracts/       # YAML contract definitions
│   └── README.md
├── tests/
└── k8s/
```

## Contract Definition Format (YAML)
Contracts are YAML files (stored in git, synced to platform). Each specifies:
- **metadata** — name, version, description, owner (team + contact), tags
- **schema** — expected columns: name, type, nullable, description, constraints (enum values, min/max, regex)
- **quality** — freshness (max staleness), volume (min/max row count, max % change), completeness (max null % per column), uniqueness (unique columns)
- **sla** — update_frequency (e.g., "every 1 hour"), max_latency (e.g., "30 minutes"), availability (e.g., "99.5%")
- **consumers** — list of teams/systems depending on this contract
- **lineage** — upstream sources and downstream dependents (optional, can be auto-discovered)

## Data Models

### Contract
- `id`, `name`, `dataset` (FQN of table/topic)
- `owner_team`, `owner_contact`
- `status` — enum: draft, active, deprecated, archived
- `current_version_id`, `created_at`, `updated_at`

### ContractVersion
- `id`, `contract_id`, `version` (semver string, e.g., "2.1.0")
- `schema_spec` — JSONB: column definitions with types, constraints
- `quality_spec` — JSONB: freshness, volume, completeness, uniqueness rules
- `sla_spec` — JSONB: frequency, latency, availability targets
- `consumers` — list of subscriber teams
- `changelog` — what changed from previous version
- `published_at`

### Violation
- `id`, `contract_id`, `version_id`
- `violation_type` — enum: schema_mismatch, quality_failure, sla_breach
- `severity` — enum: warning, error, critical
- `details` — JSONB: what specifically failed
- `detected_at`, `resolved_at`, `resolved_by`

### SLARecord
- `contract_id`, `period_start`, `period_end`
- `expected_updates`, `actual_updates`, `missed_updates`
- `max_observed_latency`, `availability_pct`, `compliant` (boolean)

## Core Logic

### Contract Management (`src/contracts/`)
- **Parser** — Read YAML contract files, validate structure, return Contract + ContractVersion models.
- **VersionManager** — Compare new version to previous. Breaking changes (column removal, type change, tightened constraints) → bump major version. Non-breaking (new column, loosened constraints, doc updates) → bump minor. Patch for metadata-only changes.
- **Differ** — Generate human-readable diff between two contract versions.
- **Registry** — CRUD on contracts and versions, search by dataset/owner/tag.

### Schema Validation (`src/schemas/`)
- **SchemaValidator** — Given a contract's schema spec and actual table metadata (from `information_schema` or a data sample): check all required columns exist, types match, constraints hold (nullability, enums, ranges). Uses JSON Schema internally.

### Runtime Enforcement (`src/enforcement/`)
- **ContractChecker** — Orchestrates all checks for a contract: (1) schema check, (2) quality check (freshness, volume, completeness, uniqueness), (3) SLA check. Returns list of Violations or empty if compliant.
- **WebhookTrigger** — Called from Airflow post-task hooks, dbt post-run hooks, or CI pipelines. Receives dataset identifier, runs check, returns pass/fail.
- **GEIntegration** — Translate contract quality specs into Great Expectations expectation suites. Run suites, collect results, map back to violations.

### Governance (`src/governance/`)
- **OwnershipRegistry** — Map teams → contracted datasets. Answer: "who owns this table?", "what does Team X own?", "who consumes this dataset?"
- **AuditLogger** — Log every contract change, violation, enforcement run. Immutable append-only.
- **LineageLinker** — If Memgraph available (from Project 2): link contracts to lineage nodes. Otherwise, maintain simple dependency list.

### Notifications (`src/notifications/`)
- **ViolationAlerter** — On violation: Slack message to contract owner with name, type, severity, details, dashboard link.
- **SLABreachNotifier** — On SLA miss: notify both owner and all consumers.

## Simulation

### seed.py
- 15 contracts covering e-commerce domain (orders, customers, payments, products, inventory, sessions, etc.)
- 5 teams (data-platform, commerce, payments, analytics, marketing)
- 3 versions per contract showing evolution
- 60 days of SLA records (mostly compliant, occasional breaches)
- 30 historical violations (mix of schema, quality, SLA)

### simulator.py (continuous)
- Every 30-60 seconds: run enforcement on a random dataset
- 75% pass, 15% quality violations, 7% SLA breaches, 3% schema violations
- On violation: create record, trigger notification
- Periodically simulate contract update (new version, breaking change detected)

### sample_contracts/
- 15 YAML files, one per contracted dataset
- Realistic column definitions, quality thresholds, SLA targets
- Cross-references between contracts (consumer lists)

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/contracts` | List contracts (filterable) |
| POST | `/api/v1/contracts` | Create contract |
| GET | `/api/v1/contracts/{id}` | Contract + current version |
| POST | `/api/v1/contracts/{id}/versions` | Publish new version (auto-detect breaking) |
| GET | `/api/v1/contracts/{id}/versions` | Version history |
| GET | `/api/v1/contracts/{id}/diff/{v1}/{v2}` | Diff two versions |
| POST | `/api/v1/enforce/{dataset}` | Run contract check |
| GET | `/api/v1/violations` | List violations (filterable) |
| GET | `/api/v1/sla/{contract_id}` | SLA compliance history |
| GET | `/api/v1/ownership` | Ownership map |
| POST | `/api/v1/webhooks/enforce` | CI/pipeline webhook |
| GET | `/health` | Health check |

## Docker Compose Services
- `app` — FastAPI
- `postgres` — Contract store, violations, SLA records
- `frontend` — Next.js
- `memgraph` (optional) — Ownership/dependency graph

## Implementation Phases

### Phase 1: Contract Model + CRUD
YAML parser, contract/version models, PostgreSQL schema, REST CRUD, seed.py. **Success:** create and retrieve contracts.

### Phase 2: Schema Validation
SchemaValidator, compare contract vs actual table. **Success:** detect column type mismatch.

### Phase 3: Quality + SLA Enforcement
ContractChecker, GE integration, SLA tracking. **Success:** enforcement returns violations for non-compliant dataset.

### Phase 4: Versioning + Breaking Change Detection
VersionManager, differ, auto version bump. **Success:** breaking change → major version increment with diff.

### Phase 5: Notifications + Governance
Slack alerts, ownership registry, audit log. **Success:** violation triggers Slack to correct team.

### Phase 6: Frontend + Simulation
Contract catalog UI, violation dashboard, simulator.py. **Success:** full demo with live enforcement.

## Metrics
- Enforcement latency: < 30 seconds per contract
- Violation detection accuracy: > 95%
- SLA tracking accuracy: 100% (deterministic)