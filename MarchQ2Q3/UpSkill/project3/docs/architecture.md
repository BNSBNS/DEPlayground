# Architecture

## Overview

The Autonomous Data Engineer Agent is a LangGraph-based state machine that
automatically detects, diagnoses, and fixes data pipeline failures.

## Flow

```
Pipeline Failure Event
        |
        v
  [parse_event] -- classify error type via regex
        |
        v
  [gather_context] -- query error history, schema info
        |
        v
  [diagnose] -- map error type to diagnosis category
        |
        v
  [generate_fixes] -- template SQL/dbt fixes, optional LLM fallback
        |
        v
  [validate] -- sqlparse syntax, dbt Jinja validation
        |           |
        |   (fail, retry < 3)
        |           |
        v           v
  [check_safety] -- forbidden patterns, protected tables, risk tier
        |
        v
  [create_pr] -- GitHub API: branch, commit, open PR
        |
        v
  [notify] -- Slack webhook with diagnosis + PR link
        |
        v
       END
```

## Key Design Decisions

1. **Template-first fixes**: SQL ALTER/UPDATE and dbt patches are generated from
   templates. LLM is only used as a fallback for unrecognized patterns.

2. **Safety model**: Three layers of protection -- forbidden SQL patterns,
   protected table list, and risk tier classification.

3. **Retry loop**: If validation fails, the agent retries fix generation up to
   `max_iterations` (default 3) before escalating.

4. **Simulation mode**: All external actions (GitHub, Slack) are logged instead
   of executed when `SIMULATION_MODE=true`.

## Components

| Layer | Purpose |
|-------|---------|
| `src/analysis/` | Error classification, log parsing, context building |
| `src/generators/` | SQL/dbt fix generation, PR descriptions |
| `src/validators/` | SQL syntax, dbt validation, safety checks |
| `src/agent/` | LangGraph state machine definition |
| `src/actions/` | GitHub PR creation, Slack notifications |
| `src/api/` | FastAPI REST endpoints |
| `src/llm/` | LLM provider abstraction (Ollama) |
| `simulation/` | Event simulation and sample dbt project |
