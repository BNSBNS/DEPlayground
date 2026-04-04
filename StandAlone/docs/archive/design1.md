# For Claude Code: structured learning plan with topics, notebooks, and projects.

---

# YOUR T-SHAPE

## Vertical: AI Data Platform Engineering

Your last 4 roles tell the story:

```
GovTech MOM    → Architected GraphRAG system POC→Production, AI eval pipelines
Tencent Games  → Managed K8s clusters, databases, Airflow/Spark/Hive at scale
AI Singapore   → Built ML training/fine-tuning pipelines on HPC, MLFlow, W&B
Rakuten        → Kafka streaming, K8s infrastructure, CI/CD, monitoring stacks
```

You build the platform layer that enables AI and data teams to ship.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ HORIZONTAL (breadth)
Python │ SQL │ Linux │ DSA │ Cloud │ Systems │ Trading domain
       │
       │  VERTICAL (depth) — AI Data Platform Engineering
       │
       │  ├── Data pipeline architecture (Airflow, Spark, Kafka, ETL)
       │  ├── Infrastructure for ML/AI (K8s, GPU clusters, HPC, Docker)
       │  ├── ML platform tooling (MLFlow, W&B, experiment tracking, RAGAs)
       │  ├── Database platform (optimization, migrations, tooling, auditing)
       │  ├── AI system deployment (LLMs, RAG, evaluation, serving)
       │  ├── Monitoring & observability (Grafana, Prometheus, alerting)
       │  └── Production reliability (L1/L2, data quality, SLAs)
       │
       ▼  Trading domain = differentiator ON TOP of this vertical
```

## Your Edgewater FX Experience

This is NOT your vertical — it's your **secret weapon**. 3 years on an
institutional FX desk gives you domain fluency that pure platform
engineers don't have. When you apply to trading firms, this separates
you from every other platform engineer in the stack.

Use it as a differentiator, not as your identity.

## Where this T maps to roles

### Trading firms (Singapore)
| Firm | Target role | Why you fit |
|------|------------|-------------|
| HRT | R&D Platform Engineer, Data Software Engineer | R&D division = "storage, clusters, job scheduling, data ETL, research tools" — your exact stack |
| Citadel | Platform Engineer, Data Infrastructure | K8s, databases, pipeline orchestration at scale |
| Grasshopper | SWE (Python), Platform Engineer | In-house trading platform, infra + data |
| Optiver | Platform / Infrastructure Engineer | Build-and-own culture, production systems |

### Broader market (your T opens these too)
| Type | Example firms | Target role |
|------|--------------|-------------|
| AI companies | Anthropic, OpenAI, Cohere | AI Infrastructure / Platform Engineer |
| Big tech | Google, Meta, ByteDance | Data Platform / ML Infrastructure |
| Scale-ups | Grab, Sea, Shopee | Data Platform Engineer |
| Finance + AI | GIC, Temasek, DBS (AI teams) | AI/Data Platform Engineer |

---

# GAP ANALYSIS

## What you have vs what tier-1 firms need

| Skill | You Now | Needed | Gap |
|-------|---------|--------|-----|
| Python proficiency | Strong | Strong | ✅ OK |
| Python INTERNALS (how list/dict/GIL work) | Unclear | Deep | 🔴 FILL |
| SQL (window funcs, query plans) | Good | Strong | ⚠️ FILL |
| Data pipelines (Airflow, Spark, Kafka) | Strong | Strong | ✅ OK |
| DSA (algorithms, data structures) | Weak signal | Medium+ | 🔴 FILL |
| Systems fundamentals (memory, I/O, processes) | Unclear | Required | 🔴 FILL |
| Linux command line | Working | Fluent | ⚠️ FILL |
| K8s / cloud infrastructure | Strong | Strong | ✅ OK |
| ML platform (MLFlow, W&B, eval) | Strong | Strong | ✅ OK |
| AI systems (RAG, LLMs, fine-tuning) | Strong | Strong | ✅ OK |
| Database internals (indexes, query plans) | DBA exposure | Deeper | ⚠️ FILL |
| Concurrency (locks, async, multiprocessing) | Some | Deeper | ⚠️ FILL |
| Trading domain knowledge | Strong (FX) | Bonus | ✅ EDGE |
| Communication | Unknown | Critical | Practice |
| DFS/BFS | Gap | Required | 🔴 FILL |
| Dynamic programming | Gap | Required (Citadel) | 🔴 FILL |

## Resume adjustments

1. Lead your summary with "AI Data Platform Engineer" not just "Data Engineer"
2. Reframe each role around platform/infrastructure impact, not task lists
3. Add metrics: data volumes processed, cluster sizes managed, pipeline SLAs
4. Position Edgewater as domain expertise, not just work history
5. Trim the tech skills table — group by platform layer, not by category

---

# LEARNING PATH

## Phase 1 — Foundation Repair (Weeks 1-2)

### 1.1 Python Internals

**WHY:** HRT's #1 fail reason. Citadel tests it. Every firm probes depth.

**STUDY:** `PYTHON_CS_FUNDAMENTALS.md` Level 1 and Level 2

**Must know cold:**
- [ ] list = array of pointers, growth formula, amortized O(1) append
- [ ] dict = hash table, open addressing, O(1) average, resize at 2/3
- [ ] set = dict without values, O(1) membership
- [ ] GIL: one thread at a time, released during I/O, multiprocessing for CPU
- [ ] Reference counting + cyclic GC + generational collection
- [ ] Generators = lazy, constant memory. List comp = eager, full RAM.
- [ ] Mutable default argument bug
- [ ] Shallow vs deep copy

**NOTEBOOK:** `01_python_internals.py`
```
1. Measure list growth: append 1M items, log sys.getsizeof at each reallocation
2. Benchmark set vs list lookup for 100K elements
3. Demonstrate GIL: threading vs multiprocessing for CPU-bound work
4. Show circular reference memory leak with gc module
5. Compare generator vs list memory for 10M items
```

### 1.2 DSA — Core Patterns

**WHY:** Every firm's OA filters on this. Grasshopper = DFS. Citadel = DP.

**STUDY:** `PYTHON_CS_FUNDAMENTALS.md` Level 3 and Level 4

**Priority order:**
- [ ] Hash map (Two Sum LC 1, Group Anagrams LC 49)
- [ ] Sliding window (Longest Substring LC 3, Max Subarray Sum)
- [ ] DFS/BFS (Number of Islands LC 200, Binary Tree Level Order LC 102)
- [ ] Two pointers (sorted array problems)
- [ ] Binary search (LC 704)
- [ ] Stack (Valid Parentheses LC 20)
- [ ] Dynamic programming (Climbing Stairs LC 70, Coin Change LC 322)
- [ ] Heap (Find Median from Data Stream LC 295 — HRT asked this)
- [ ] Prefix sum (range queries)

**NOTEBOOK:** `02_dsa_patterns.py`
```
Timed practice (simulate OA):
1. Two Sum (LC 1) — 5 min target
2. Group Anagrams (LC 49) — 10 min target
3. Longest Substring (LC 3) — 10 min target
4. Number of Islands (LC 200) — 15 min target ← Grasshopper
5. Climbing Stairs (LC 70) — 5 min target ← Citadel
6. Coin Change (LC 322) — 15 min target ← Citadel
7. Valid Parentheses (LC 20) — 5 min target
8. Median from Data Stream (LC 295) — 15 min target ← HRT
9. Merge Intervals (LC 56) — 10 min target
10. Binary Search (LC 704) — 5 min target
```

### 1.3 Systems Fundamentals

**WHY:** HRT explicitly requires this for Python roles. Optiver tests
concurrency. Platform engineers MUST understand the stack.

**STUDY:** `HRT_FINAL_PREP.md` sections 1B and 1C

**Must know:**
- [ ] Virtual memory (pages, page faults, swapping, OOM killer)
- [ ] Stack vs heap (function frames vs Python objects)
- [ ] File descriptors (fd table, limits, "too many open files")
- [ ] Buffered I/O (userspace buffer → kernel page cache → disk → fsync)
- [ ] Process vs thread (isolation, GIL, creation cost, IPC)
- [ ] Sequential vs random I/O (why columnar formats are faster)
- [ ] Full chain: what happens when pd.read_csv() runs

**NOTEBOOK:** `03_systems_fundamentals.py`
```
1. Open files without closing until fd limit → catch OSError → fix with 'with'
2. Compare sequential vs random read performance
3. Measure memory of process vs thread creation
4. Profile a pipeline: is it CPU-bound, I/O-bound, or memory-bound?
```

---

## Phase 2 — Data Platform Skills (Weeks 3-4)

### 2.1 SQL Mastery

**WHY:** Citadel tests SQL hard. Platform engineers write complex queries daily.

**STUDY:** `HRT_FINAL_PREP.md` sections 2C

**Topics:**
- [ ] Window functions (ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD)
- [ ] CTEs — why you need them for window function filtering
- [ ] SQL execution order (FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY)
- [ ] Reconciliation patterns (LEFT JOIN WHERE NULL, FULL OUTER JOIN)
- [ ] EXPLAIN ANALYZE (reading query plans, identifying bottlenecks)
- [ ] Index design (B-tree, composite, covering indexes)
- [ ] Partitioning (range by date, list by symbol/region)

**NOTEBOOK:** `04_sql_mastery.sql`
```
1. Reconciliation query (find mismatches between two tables)
2. Gap detection using LAG
3. Top-N per group using ROW_NUMBER
4. Moving average using window frames
5. Compare EXPLAIN plans: indexed vs non-indexed
6. Design a partitioned table for time-series data
```

### 2.2 Database Internals

**WHY:** You were DBA at Tencent. Deepen this into a platform strength.

**Topics:**
- [ ] B-tree indexes (structure, when to use, composite key ordering)
- [ ] Hash indexes (when they beat B-tree)
- [ ] Query planner (how PostgreSQL picks an execution plan)
- [ ] EXPLAIN ANALYZE deep dive (seq scan, index scan, join strategies)
- [ ] WAL (write-ahead logging) and crash recovery
- [ ] Connection pooling (pgbouncer, why it matters at scale)
- [ ] MVCC (how PostgreSQL handles concurrent reads/writes)
- [ ] Vacuum and bloat management

**NOTEBOOK:** `05_database_internals.py`
```
1. Create 10M row table, compare query time with/without indexes
2. Read EXPLAIN ANALYZE output, identify the bottleneck
3. Benchmark nested loop vs hash join
4. Implement range partitioning by date
```

### 2.3 Pandas and Data Quality

**WHY:** Data quality is critical for platform reliability. OAs may test pandas.

**STUDY:** `HRT_FINAL_PREP.md` section 2B

**Topics:**
- [ ] DataFrame internals (numpy arrays per column, vectorized ops)
- [ ] groupby: transform vs agg
- [ ] merge (left_on, right_on, how=, detecting unmatched keys)
- [ ] Outlier detection (rolling stats, z-score)
- [ ] Deduplication patterns
- [ ] Chunked reading for large files
- [ ] Data quality gates (schema → completeness → reasonableness → cross-validation)

**NOTEBOOK:** `06_pandas_data_quality.py`
```
1. Build a reusable sanity_check(df) function
2. VWAP calculation
3. Outlier detection with rolling mean + std
4. Reconciliation: compare two DataFrames, find mismatches
5. Process a large file in chunks
```

---

## Phase 3 — Platform Depth (Weeks 5-6)

### 3.1 Concurrency and Performance

**WHY:** Platform engineers must understand concurrent systems. Optiver
and Citadel test this. Your pipelines run in parallel.

**Topics:**
- [ ] threading (locks, RLock, race conditions, deadlock)
- [ ] multiprocessing (Pool, shared memory, IPC overhead)
- [ ] asyncio (event loop, coroutines, aiohttp, gather)
- [ ] Producer-consumer pattern (queue.Queue, pipeline stages)
- [ ] Lock ordering (deadlock prevention)
- [ ] GIL interaction with each approach

**NOTEBOOK:** `07_concurrency.py`
```
1. Write a race condition, then fix with a lock
2. Producer-consumer with queue.Queue
3. Fetch 20 URLs concurrently: threading vs asyncio vs sequential
4. multiprocessing.Pool for CPU-bound data transformation
5. Demonstrate and fix a deadlock
```

### 3.2 Pipeline Architecture and Orchestration

**WHY:** This is your bread and butter. Make sure you can articulate it deeply.

**Topics:**
- [ ] DAG design (Airflow concepts: operators, sensors, XCom, retries)
- [ ] Idempotency (why pipelines must be re-runnable safely)
- [ ] Backfill strategies (reprocessing historical data)
- [ ] Data lineage (where did this data come from, what transformed it)
- [ ] Schema evolution (handling format changes without breaking downstream)
- [ ] Exactly-once vs at-least-once delivery
- [ ] Monitoring and alerting (SLA tracking, anomaly detection)

**NOTEBOOK:** `08_pipeline_architecture.md`
```
Write out your answers to these interview questions:
1. "How would you design a pipeline that ingests data from 5 vendors?"
2. "A vendor changes their schema. How do you handle it?"
3. "How do you ensure idempotency in your ETL?"
4. "Your pipeline processes 10M rows daily. It needs to scale to 100M. What changes?"
5. "How do you monitor pipeline health and set SLAs?"
```

### 3.3 ML Platform and AI Infrastructure

**WHY:** This is where your GovTech and AI Singapore experience converge.
Deepening this makes your vertical sharper.

**Topics:**
- [ ] Experiment tracking (MLFlow, W&B — you know these, formalize it)
- [ ] Model serving (FastAPI, TorchServe, Triton — latency considerations)
- [ ] Feature stores (concept, when to use)
- [ ] GPU cluster management (scheduling, resource allocation, spot instances)
- [ ] LLM deployment (quantization, batching, KV-cache)
- [ ] Evaluation pipelines (RAGAs, custom metrics, A/B testing)
- [ ] RAG architecture (chunking, embedding, retrieval, reranking)

**NOTEBOOK:** `09_ml_platform.md`
```
Write out your architecture decisions for:
1. "Design an experiment tracking system for 10 researchers"
2. "How would you serve an LLM with <200ms P99 latency?"
3. "Design a RAG evaluation pipeline" (you built this — formalize it)
4. "A model's accuracy drops in production. How do you detect and debug?"
```

---

## Phase 4 — DFS/BFS + DP Deep Dive (Week 7)

### 4.1 DFS/BFS (Grasshopper's go-to)

**NOTEBOOK:** `10_dfs_bfs.py`
```
Must-solve:
1. Number of Islands (LC 200) — grid DFS ← Grasshopper pattern
2. Binary Tree Level Order Traversal (LC 102) — BFS
3. Clone Graph (LC 133) — DFS + hash map
4. Max Depth of Binary Tree (LC 104) — simple DFS
5. Word Search (LC 79) — backtracking DFS
```

DFS template:
```python
def dfs(graph, start):
    visited = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited: continue
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                stack.append(neighbor)
    return visited
```

BFS template:
```python
from collections import deque
def bfs(graph, start):
    visited = set([start])
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited
```

### 4.2 Dynamic Programming (Citadel's #1)

**NOTEBOOK:** `11_dynamic_programming.py`
```
Must-solve:
1. Climbing Stairs (LC 70) — 1D DP intro
2. Coin Change (LC 322) — classic DP
3. House Robber (LC 198) — 1D DP
4. Longest Common Subsequence (LC 1143) — 2D DP
5. Unique Paths (LC 62) — 2D DP grid

DP pattern:
1. Define state: dp[i] = answer for subproblem i
2. Find recurrence: dp[i] = f(dp[i-1], dp[i-2], ...)
3. Base case: dp[0] = ...
4. Build bottom-up (iterate) or top-down (memoize)
5. Answer = dp[n]
```

---

## Phase 5 — Interview Readiness (Weeks 8-10)

### 5.1 Behavioral Prep

**Your "tell me about yourself" (2 min, practice out loud):**

"I'm an AI Data Platform Engineer with 4+ years building the infrastructure
that enables data and AI teams to ship. Most recently at GovTech I
architected a GraphRAG system from POC to production — owning the graph
database layer, the AI evaluation pipeline, and the deployment. Before
that I managed data platforms at Tencent Games — K8s clusters, databases,
Airflow orchestration, and built tooling that other teams relied on daily.

What makes my background a bit different is that before I moved into
engineering, I spent 3 years on an institutional FX trading desk managing
liquidity for hedge funds and prop desks. So I understand both sides — how
to build reliable data systems, and what it feels like when those systems
fail while you're trying to trade."

**Other stories to prepare:**
- [ ] "Data quality issue you found and fixed" — draw from Tencent migrations
- [ ] "System you built that other teams depended on" — database auditor at Tencent
- [ ] "Scaling challenge" — GraphRAG POC to POV at GovTech
- [ ] "Working under pressure" — production support, or trading desk stories
- [ ] "Working with stakeholders" — vendors, internal teams, researchers

### 5.2 Data Debugging (for HRT specifically)

**STUDY:** `HRT_FINAL_PREP.md` section 1A

Practice these scenarios OUT LOUD:
- [ ] "15 tickers show zero prices since yesterday"
- [ ] "Pipeline normally takes 10 min, running 2 hours"
- [ ] "Researcher says volume data looks wrong since Tuesday"

### 5.3 Company-Specific Prep

**HRT (R&D Platform / Data Software Engineer):**
- Read both blog posts on engineering and interviewing
- Their R&D division handles storage, clusters, scheduling, ETL, research tools
- Emphasize: K8s/infra experience + data pipeline skills + trading background
- Prep: coding OA → phone screen → onsite (coding + debugging + design + culture)

**Citadel (Platform Engineer / Data Infrastructure):**
- HackerRank OA: DP heavy + multiple choice (caching, systems)
- System design round: design data infrastructure for trading teams
- Emphasize: database platform work at Tencent, scale experience
- Prep: DP patterns + system design + modular arithmetic

**Grasshopper (SWE / Platform):**
- HackerRank: 2 hrs, DFS + string parsing, edge case coverage matters
- 2-3 rounds: live coding (C++ knowledge if applicable), BQ
- Emphasize: platform building, in-house tool development
- Prep: DFS/BFS + thorough edge case handling

**Optiver (Platform / Infrastructure):**
- 80-min HackerRank → pair programming → system design (latency focus)
- Emphasize: K8s infrastructure, monitoring, production reliability
- Prep: concurrency, low-latency design, pair programming communication

### 5.4 Mock Interview Schedule

- [ ] Week 8: 2 timed LeetCode mediums in 40 min (simulate OA)
- [ ] Week 8: Record yourself doing data debugging scenario
- [ ] Week 9: SQL reconciliation query from memory in 5 min
- [ ] Week 9: System design: "design a data pipeline for 5 vendors"
- [ ] Week 10: Full mock: behavioral + coding + system design (2 hrs)

---

# PROJECT PORTFOLIO

## What to build and put on GitHub

### Project 1: AI Data Platform Components (shows your vertical)
```
ai-data-platform/
├── README.md
├── pipeline/
│   ├── ingestion/         # multi-source data ingestion
│   ├── quality/           # schema, completeness, reasonableness checks
│   ├── reconciliation/    # compare sources, find mismatches
│   └── orchestrator.py    # simple DAG runner or Airflow integration
├── ml_platform/
│   ├── experiment_tracker/ # lightweight MLFlow-style tracking
│   ├── evaluation/        # metrics computation, comparison
│   └── serving/           # FastAPI model serving endpoint
├── infrastructure/
│   ├── docker-compose.yml # local dev environment
│   ├── k8s/               # K8s manifests
│   └── monitoring/        # Prometheus + Grafana configs
├── database/
│   ├── schema.sql         # partitioned tables, indexes
│   ├── migrations/        # schema evolution
│   └── queries/           # optimized analytical queries
└── tests/
```

### Project 2: Market Data Quality Engine (shows trading domain edge)
```
market-data-quality/
├── README.md
├── fetchers/              # fetch from 2+ financial data APIs
├── parsers/               # normalize different formats
├── quality_gates/         # schema → completeness → reasonableness
├── reconciliation/        # cross-source comparison
├── monitoring/            # alerting on anomalies
├── api/                   # FastAPI status/query endpoint
└── tests/
```

### Project 3: DSA Solutions (shows coding ability)
```
dsa-solutions/
├── README.md
├── hash_map/              # two sum, group anagrams
├── sliding_window/        # longest substring, max subarray
├── dfs_bfs/               # number of islands, tree traversal
├── dynamic_programming/   # climbing stairs, coin change, LCS
├── heap/                  # median from stream, top-K
└── tests/                 # every solution tested with edge cases
```

---

# FILES INVENTORY

| File | What it covers | Status |
|------|---------------|--------|
| `HRT_FINAL_PREP.md` | HRT-specific interview prep, all code validated | ✅ 22/22 tests pass |
| `PYTHON_CS_FUNDAMENTALS.md` | Python/CS foundations, 8 levels with self-tests | ✅ 74/75 tests pass |
| `LEARNING_ROADMAP.md` | This file: career direction, gap analysis, learning path | ✅ Current |

---

# TIMELINE

```
Week 1-2:  Foundation (Python internals, DSA patterns, systems)
Week 3-4:  Data platform skills (SQL, database internals, pandas/quality)
Week 5-6:  Platform depth (concurrency, pipeline architecture, ML platform)
Week 7:    DFS/BFS + DP deep dive
Week 8-10: Interview readiness + mock interviews + projects

Total: ~10 weeks at 1-2 hours/day
Accelerated: ~6 weeks at 2-3 hours/day
```

## If you only have 2 weeks before an interview:
1. Python internals (fundamentals doc Level 1-2)
2. DSA: Two Sum, Median, DFS, one DP problem
3. SQL reconciliation + window functions
4. Data debugging out loud (3 scenarios)
5. "Tell me about yourself" pitch practiced out loud

---

# POSITIONING STATEMENT

When someone asks "what do you do?":

"I'm an AI Data Platform Engineer. I build the infrastructure that
enables data and AI teams to ship — pipelines, databases, ML platforms,
monitoring. I've done this at scale across government AI systems,
gaming data platforms, and ML research environments. My earlier career
on an institutional FX trading desk gives me domain fluency that most
platform engineers don't have."

That's your T. Own it.