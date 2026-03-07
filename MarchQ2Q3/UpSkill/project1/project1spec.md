# Project 1: AI Data Observability & Root Cause Intelligence Platform

## What This Is
A platform that monitors data pipelines for quality issues (staleness, volume anomalies, schema drift), traces data lineage to determine blast radius, performs root cause analysis by correlating alerts with lineage, and can auto-remediate common failures.

## Career Relevance
- **Data Engineering:** Core competency — monitoring pipeline health is a senior DE responsibility
- **ML Engineering:** ML models silently degrade when training data quality drops; this catches it. Feature freshness monitoring ties directly into Project 6.
- **Platform Engineering:** This is the reliability layer every platform team builds first
- Anomaly detection (z-score, KS test) demonstrates statistical thinking valued across all roles

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Orchestration events | Airflow | Receives failure callbacks via webhooks |
| Data quality | Great Expectations | Expectation suites for validation |
| Lineage events | OpenLineage | Standard event format |
| Metadata store | PostgreSQL | Metrics, alerts, config |
| Graph (optional) | Memgraph | Lineage traversal. `neo4j` Python driver connects via Bolt protocol. |
| API | FastAPI | Webhook receivers, REST endpoints |
| Monitoring | Prometheus + Grafana | Dashboards, alerting |
| Notifications | Slack (webhook) | Alert delivery |

## Folder Structure

```
data-observability/
├── docker-compose.yml          # app, postgres, memgraph, prometheus, grafana
├── pyproject.toml
├── .env.example
├── Makefile
├── README.md
├── src/
│   ├── config.py
│   ├── models/                 # DataQualityMetric, Alert, LineageNode/Edge, RemediationLog
│   ├── collectors/             # Ingest from Airflow, dbt, GE, OpenLineage
│   ├── detectors/              # Freshness, volume, distribution, schema drift
│   ├── lineage/                # In-memory graph + optional Memgraph persistence
│   ├── reasoning/              # Root cause engine, cross-signal correlator
│   ├── remediation/            # Playbooks, executor, approval gates
│   ├── alerting/               # Router, Slack notifier
│   ├── api/
│   └── db/
├── simulation/
│   ├── seed.py                 # Sample tables, 30 days of metrics, lineage graph
│   ├── simulator.py            # Continuous: inject failures, drift, volume spikes
│   ├── fixtures/
│   └── README.md
├── tests/
├── grafana/dashboards/
├── prometheus/
└── k8s/
```

## Data Models

### DataQualityMetric
- `table_name`, `database`, `schema_name`
- `metric_type` — enum: freshness, volume, distribution, schema, custom
- `value` — measured value (staleness in minutes, row count, etc.)
- `expected_value` — baseline
- `threshold_warning`, `threshold_critical`
- `status` — enum: healthy, warning, critical, unknown. Derived: value vs thresholds.
- `metadata` — JSONB for detector-specific context
- `measured_at`

### Alert
- `title`, `description`, `severity` (info/warning/critical)
- `state` — enum: open, acknowledged, resolved, suppressed
- `source_table`, `source_metric_type`
- `root_cause`, `suggested_remediation`
- `created_at`, `acknowledged_at`, `resolved_at`

### LineageNode / LineageEdge
- Node: `id` (FQN), `name`, `node_type` (table/view/dbt_model/dashboard/metric/pipeline), `owner`, `tags`
- Edge: `source_id`, `target_id`, `relationship` (depends_on/derived_from/feeds_into), `transformation`

### RemediationLog
- `alert_id`, `action_type`, `action_detail` (JSONB), `executed_by`, `result` (success/failed/skipped), `executed_at`

## Core Logic

### Detectors (`src/detectors/`)
Each takes a table reference, returns a DataQualityMetric.

- **FreshnessDetector** — Query `MAX(timestamp_column)`, compute staleness in minutes vs configurable thresholds.
- **VolumeDetector** — Compare current `COUNT(*)` against a rolling window of historical counts using z-score. Configurable: lookback period (default 14 days), warning z-score (default 2.0), critical z-score (default 3.0). Requires 3+ historical data points; returns status=unknown otherwise.
- **SchemaDetector** — Read `information_schema.columns`, diff against last stored snapshot. Additions → warning, removals/type changes → critical. Store new snapshot after each check.
- **DistributionDetector** — Compute basic stats for numeric columns (mean, stdev, min, max, null%). Compare against stored profile using Kolmogorov-Smirnov test. KS p-value < 0.01 → critical, < 0.05 → warning.

### Lineage Graph (`src/lineage/`)
- In-memory directed graph using adjacency lists (dict of sets)
- BFS traversal for `get_upstream(node_id, max_depth)` and `get_downstream(node_id, max_depth)`
- `get_impact_summary(node_id)` → counts of affected tables, dashboards, metrics
- Optional: persist to Memgraph for complex Cypher traversals

### Root Cause Engine (`src/reasoning/`)
- Gather all active alerts within a correlation window (configurable, default 30 min)
- Map alerts to lineage nodes
- Walk upstream from trigger alert; the deepest upstream node with an active alert = probable root cause
- If no upstream alerts, the trigger itself is the origin
- Confidence: base 0.6 for self-origin, increases with corroborating evidence
- Returns: cause description, confidence, evidence list, affected downstream, suggested actions

### Remediation (`src/remediation/`)
- Playbooks: condition → action mappings (e.g., freshness critical → rerun Airflow DAG)
- Executor: dry-run first, then execute
- Two tiers: auto-execute (low risk) vs require-approval (high risk)
- All actions logged to remediation_log table

## Simulation

### seed.py
- Create 5 databases, 20+ tables with realistic names (orders, customers, payments, products, sessions, etc.)
- Generate 30 days of historical metrics with normal patterns (slight daily/weekly seasonality)
- Build a lineage graph: 30+ nodes with realistic dependencies
- Seed 5-10 resolved alerts as history

### simulator.py (continuous)
- Every 30-60 seconds: generate a metric check for a random table
- Distribution: 80% healthy, 10% warning, 10% critical
- Periodically inject: volume spike (3x normal), schema drift (add/remove column), freshness timeout
- When critical metrics fire: auto-create alerts, trigger RCA
- Log all events for real-time observation

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/metrics/check` | Run a quality check |
| GET | `/api/v1/metrics` | Query historical metrics (filterable) |
| GET | `/api/v1/alerts` | List alerts (filter by state, severity) |
| POST | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert |
| GET | `/api/v1/lineage/{node_id}/upstream` | Upstream dependencies |
| GET | `/api/v1/lineage/{node_id}/downstream` | Downstream dependencies |
| GET | `/api/v1/lineage/{node_id}/impact` | Impact summary |
| POST | `/api/v1/rca/{alert_id}` | Trigger root cause analysis |
| POST | `/api/v1/webhooks/airflow` | Airflow failure callback |
| POST | `/api/v1/webhooks/openlineage` | OpenLineage events |
| GET | `/health` | Health check |

## Database (PostgreSQL)
Tables: `data_quality_metrics`, `schema_snapshots`, `alerts`, `lineage_edges`, `remediation_log`. UUIDs as PKs, JSONB for metadata, indexes on (table_name, database, metric_type) and (measured_at DESC).

## Docker Compose Services
- `app` — FastAPI service
- `postgres` — PostgreSQL 16
- `memgraph` — `memgraph/memgraph-platform:latest` (Bolt 7687, Lab UI 3000)
- `prometheus` — metrics collection
- `grafana` — dashboards

## Implementation Phases

### Phase 1: Detectors + API
Three core detectors (freshness, volume, schema), PostgreSQL schema, metrics endpoint, unit tests. **Success:** `curl` a check endpoint, get a metric with correct status.

### Phase 2: Historical Tracking + Anomaly Detection
Store metrics over time, z-score detection with rolling windows, schema snapshot diffing. **Success:** detect a simulated volume spike.

### Phase 3: Lineage Graph
Parse dbt manifest.json, OpenLineage webhook, in-memory BFS graph, lineage endpoints. **Success:** trace upstream/downstream for any table.

### Phase 4: Root Cause Analysis
RCA engine, time-window correlation, lineage integration. **Success:** downstream alert correctly identifies upstream root cause.

### Phase 5: Alerting + Dashboards
Slack notifier, severity routing, Grafana dashboard, Prometheus export. **Success:** Slack alert within 30 seconds of detection.

### Phase 6: Remediation + Simulation
Playbooks, executor, approval gates, seed.py, simulator.py. **Success:** full demo loop running autonomously.

## SLO Targets
- Detection latency: < 2 minutes
- Alert latency: < 30 seconds
- RCA accuracy: > 80%
- False positive rate: < 10%
- API p95: < 500ms