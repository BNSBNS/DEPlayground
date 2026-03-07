# Project 3: Autonomous Data Engineer Agent

## What This Is
An AI agent that listens for pipeline failures, analyzes logs and schemas to diagnose root causes, generates SQL/dbt fixes with tests, validates them, and opens GitHub pull requests — with human approval gates for safety.

## Career Relevance
- **AI Engineering:** Agentic AI is the frontier of applied AI — building a production-grade autonomous agent is a strong differentiator
- **Platform Engineering:** Automated remediation is what separates senior platform engineers from junior ones
- **ML Engineering:** The validation/retry loop (generate → evaluate → improve) is the same pattern used in RLHF and ML model iteration
- Safety controls (guardrails, risk tiers, rate limiting) are directly applicable to responsible AI/ML deployment

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Agent framework | LangGraph | Stateful graph with conditional routing and retries |
| LLM | Provider pattern (see Master Plan) | Ollama default, swap via env var |
| Orchestration | Airflow | Event source (failure callbacks) |
| Transformations | dbt | Codebase the agent reads and patches |
| Data quality | Great Expectations | Test generation target |
| Version control | GitHub REST API | PR creation — no local git clone needed |
| Notifications | Slack (webhook + interactive) | Alerts + approval buttons |

## Folder Structure

```
data-agent/
├── docker-compose.yml          # app, postgres
├── pyproject.toml
├── .env.example
├── Makefile
├── README.md
├── docs/
│   ├── architecture.md
│   ├── safety_model.md
│   └── playbooks.md
├── src/
│   ├── config.py
│   ├── llm/                    # Provider pattern
│   ├── models/
│   ├── listeners/              # Airflow webhook, SLA monitor
│   ├── analysis/               # Log parser, schema analyzer, error classifier, context builder
│   ├── agent/                  # LangGraph graph, nodes, state
│   ├── generators/             # SQL fixer, dbt fixer, test generator, PR description
│   ├── validators/             # SQL validator, dbt validator, safety checker
│   ├── actions/                # GitHub PR, Slack notifier, approval gate
│   ├── api/
│   └── db/
├── simulation/
│   ├── seed.py                 # Sample dbt project, historical events/runs
│   ├── simulator.py            # Generate fake pipeline failures continuously
│   ├── sample_dbt_project/     # Small dbt project the agent operates on
│   ├── fixtures/
│   └── README.md
├── tests/
└── k8s/
```

## Data Models

### PipelineFailureEvent
- `source` — enum: airflow, dbt, great_expectations, custom
- `dag_id`, `task_id`, `model_name` (optional per source)
- `error_message`, `error_type` (schema_mismatch, null_violation, etc.)
- `log_snippet` (last N lines), `affected_table`
- `severity` — enum: low, medium, high, critical
- `run_id`, `occurred_at`, `metadata` (JSONB)

### Diagnosis
- `category` — enum: schema_drift, null_violation, type_mismatch, volume_anomaly, missing_source, permission_error, timeout, logic_error, unknown
- `confidence` (0.0-1.0), `explanation`, `evidence` (list of strings), `affected_objects` (list), `suggested_approach`

### GeneratedFix
- `fix_type` — enum: sql_patch, dbt_model_update, dbt_schema_update, test_addition, config_change
- `file_path`, `original_content` (null for new files), `proposed_content`, `explanation`
- `risk_level` (low/medium/high), `tests_added` (list)

### FixProposal
- `event_id`, `diagnosis`, `fixes` (list of GeneratedFix)
- `pr_title`, `pr_description`, `confidence`, `requires_approval`, `validation_results`

## Agent Architecture (LangGraph)

### State Schema
- **Input:** `event` (PipelineFailureEvent)
- **Analysis:** `logs`, `schema_diff`, `error_classification`, `context`
- **Diagnosis:** `diagnosis` (Diagnosis)
- **Generation:** `proposed_fixes` (list of GeneratedFix)
- **Validation:** `validation_passed` (bool), `validation_errors` (list)
- **Action:** `pr_url`, `notification_sent`, `requires_human_approval`
- **Control:** `iteration` (int), `max_iterations` (default 3), `error`

### Flow
```
parse_event → gather_context → diagnose → generate_fixes → validate
  → [valid] → check_safety → [needs approval] → request_approval → create_pr → notify → END
                              [auto-approve]   → create_pr → notify → END
  → [invalid + retries left] → generate_fixes (loop, pass errors as context)
  → [invalid + no retries]   → escalate → END
```

### Node Descriptions
- **parse_event** — Classify error type via regex/heuristics, initialize state.
- **gather_context** — Fetch Airflow logs (if dag_id+task_id), schema comparison on affected table, assemble context string.
- **diagnose** — LLM call with context → structured Diagnosis. Use JSON mode or XML tags for reliable parsing.
- **generate_fixes** — Based on diagnosis category: schema drift → dbt model patch, null/type → SQL fix. Always generate corresponding tests. On retry, include previous validation errors in prompt.
- **validate** — SQL syntax check (sqlparse or sqlfluff), dbt compile (subprocess). Collect all errors.
- **check_safety** — Apply safety rules (see below). Set requires_human_approval flag.
- **request_approval** — Slack interactive message. Wait for callback or timeout.
- **create_pr** — GitHub REST API: (1) GET `/repos/{owner}/{repo}/git/ref/heads/main` → SHA, (2) POST `/repos/{owner}/{repo}/git/refs` → create branch, (3) PUT `/repos/{owner}/{repo}/contents/{path}` → commit files (base64 content), (4) POST `/repos/{owner}/{repo}/pulls` → open PR.
- **notify** — Slack message: diagnosis, fix description, PR link, confidence, risk level.
- **escalate** — Slack message flagging unresolvable failure for human attention.

## Safety Controls (Implement Strictly)

### Protected Tables
Configurable set the agent NEVER modifies. Defaults: `users`, `payments`, `billing`, `auth_tokens`. Fix targeting protected table → auto-escalate, no PR.

### Forbidden SQL Operations
NEVER generate: `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, bare `DELETE FROM` (without WHERE), `GRANT`, `REVOKE`. Scan generated SQL for these patterns before validation.

### Risk Tiers
- **Low** (auto-approve): Adding columns with defaults, new tests, documentation, new dbt models
- **Medium** (require approval): Modifying existing model logic, changes > 100 lines
- **High** (require approval + flag): Production-critical models, type changes, anything touching protected tables

### Rate Limiting
Max N agent runs per hour (configurable, default 10). Dead letter queue for unresolvable events.

## Simulation

### seed.py
- Sample dbt project in `simulation/sample_dbt_project/` with 10 models, sources, tests
- 20 historical agent runs (events, diagnoses, fixes) showing successes and escalations
- Pre-populated lineage graph for the sample project

### simulator.py (continuous)
- Every 1-2 minutes: generate a realistic failure event
  - 40% schema drift (column added/removed/renamed in source)
  - 25% null violations (unexpected nulls in non-nullable columns)
  - 15% type mismatches (string in integer column)
  - 10% timeouts
  - 10% unknown/misc
- Realistic error messages sampled from templates
- If SIMULATION_MODE=true: agent processes end-to-end, but skips actual GitHub PR creation — logs the would-be PR to console and DB instead

### sample_dbt_project/
- `models/staging/` — 5 staging models (stg_orders, stg_customers, stg_payments, stg_products, stg_sessions)
- `models/marts/` — 3 mart models (fct_orders, dim_customers, dim_products)
- `models/intermediate/` — 2 intermediate models
- `schema.yml`, `sources.yml` — column definitions, tests, source declarations

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/events` | Receive failure events |
| GET | `/api/v1/runs` | List agent runs |
| GET | `/api/v1/runs/{id}` | Run detail (diagnosis, fixes, PR) |
| POST | `/api/v1/approvals/{id}/approve` | Approve fix |
| POST | `/api/v1/approvals/{id}/reject` | Reject fix |
| GET | `/health` | Health check |

## Docker Compose Services
- `app` — FastAPI + agent service
- `postgres` — Agent state, run history, event log

## Implementation Phases

### Phase 1: Event Listener + Log Parsing
Webhook receiver, log parser, error classifier, seed.py. **Success:** receive event, classify it.

### Phase 2: Context + Diagnosis
Schema analyzer, context assembler, LLM diagnosis with provider pattern. **Success:** structured diagnosis from failure event.

### Phase 3: Fix Generation + Validation
SQL/dbt generators, test generator, validators. **Success:** valid fix for a schema drift scenario.

### Phase 4: LangGraph Agent
Wire all nodes into state machine, retry loop, safety checker. **Success:** end-to-end event → validated fix.

### Phase 5: PR + Notifications
GitHub PR via REST API, Slack notifier, approval gate. **Success:** PR opened from simulated failure.

### Phase 6: Simulation + Hardening
simulator.py, rate limiting, dead letter queue, structured logging, Prometheus metrics. **Success:** agent running continuously against simulated failures.

## Metrics
- MTTR reduction: > 50%
- Auto-resolution rate: > 30%
- First-attempt validation pass: > 80%
- False positive rate: < 15%
- Time to PR: < 5 minutes
- Unauthorized writes: 0 (hard requirement)