# Cybersecurity Portfolio — Claude Code Blueprint

> 8 projects + foundations. Every project anchored to resume. Every CLAUDE.md optimized for Claude Code.

## Build Priority (MVP Path)

| Tier | Project | Dir | Resume Leverage | Time |
|------|---------|-----|-----------------|------|
| **1** | **Fraud & Anomaly Detection** | `FraudAndAnomaly/` | FX trading, ML pipelines, institutional clients | 3–4 wks |
| **1** | **SIEM Detection Engine** | `SecurityDataPipeline/` | Airflow, Spark, Kafka, ETL at scale | 3–4 wks |
| **1** | **LLM Security Firewall** | `AIMMLSecurity/` | NLP, fine-tuning, LangChain — hottest market | 3–4 wks |
| **2** | **Threat Intel Knowledge Graph** | `TIKG/` | GraphRAG + Neo4j (current GovTech role) — unique | 3–5 wks |
| **2** | **API Security Framework** | `APISecurity/` | FastAPI/Django daily — practical AppSec | 2–3 wks |
| **3** | **Network Security Monitor** | `NetworkSecurity/` | K8s, AWS/GCP/Azure, VPC, container ops | 3–4 wks |
| **3** | **Supply Chain Scanner** | `InfraScanner/` | CI/CD, Docker, K8s, jFrog Artifactory | 2–3 wks |
| **3** | **Data Security Toolkit** | `DataSecurity/` | DB auditor at Tencent, MSSQL/PG/MySQL | 3–4 wks |
| — | **Foundations** | `Foundations/` | Reference doc — read before building | — |

**Tier 1 = build first.** Covers ML security, detection engineering, and AI safety — the three highest-demand + highest-salary intersections right now. Tier 2 adds uniqueness (graph + AppSec). Tier 3 is solid but lower differentiation.

## Shared Stack

- **Python 3.13+** | `uv` + conda env | Pydantic v2 | structlog
- **Backend:** FastAPI | pytest >80% coverage | mypy strict | ruff
- **Frontend:** NextJS for Tier 1 projects | Streamlit for Tier 2/3
- **Infra:** Docker | Kafka (KRaft mode) where applicable
- **ML:** MLflow for experiment tracking (Projects 01, 05)

## Integration Points

Projects are not isolated — they share a **common alert schema** (see Foundations #8). This demonstrates systems thinking:

```
[FraudAndAnomaly] ──alert──▶ [SecurityDataPipeline (SIEM)] ◀──alert── [NetworkSecurity]
[AIMMLSecurity]   ──alert──▶ [SecurityDataPipeline (SIEM)] ◀──alert── [APISecurity]
[InfraScanner]    ──alert──▶ [SecurityDataPipeline (SIEM)]
```

Alert producers (01, 02, 05, 06, 07) emit to a shared Kafka topic. The SIEM (03) consumes, correlates, and alerts. Even implementing this for 2-3 projects is a differentiator.

## Shared Infrastructure

Projects share common patterns. To avoid duplication:
- **NVD API client:** Build in TIKG (04), reuse in InfraScanner (06)
- **FastAPI middleware:** Auth, rate limiting, logging — extract to shared utils or cookiecutter
- **HTML report generator:** Shared Jinja2 template pattern across all projects
- **CLI scaffolding:** Consistent `click` or `typer` patterns

## Claude Code Workflow

```
1. cd into project folder
2. /clear
3. "Read CLAUDE.md and phase.md"
4. Paste the phase prompt
5. Let Claude implement
6. Run the test gate
7. "Update memory.md and phase.md"
8. git commit -m "feat(phase-N): description"
9. Next phase
```

**Rules:**
- One phase per session. `/clear` between phases.
- CLAUDE.md = persistent memory. Short, explicit instructions > long docs.
- phase.md = progress tracker. memory.md = decisions + context for next session.
- Sub-agents for review (`.claude/agents/`). Don't pollute implementation context.
- Test gates are mandatory. Don't advance until tests pass.
