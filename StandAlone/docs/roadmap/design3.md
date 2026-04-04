# Design 3: Foundation-First Roadmap for Trading AI/ML Data Platform

## Purpose

This document replaces `design1.md` and `design2.md` with one integrated 12-week roadmap.

The goal is not to become "complete" in every area in 3 months. The goal is to build a strong base in the engineering fundamentals that are currently limiting depth, then apply that base to one narrow vertical:

`trading AI/ML research data platform`

This plan is intentionally foundation-first.

- First 8 weeks: build engineering fundamentals hard and properly.
- Final 4 weeks: go deep in a finance/trading-flavored AI/ML data platform slice.
- Time budget: about `7-9 hours/week`.
- Weekdays: `1 hour/day`.
- Weekends: `2-4 hours total`.

If time gets tight, cut scope from the vertical first. Do not cut Python, testing, databases, systems, or platform reliability.

---

## Your T-Shape

### Horizontal Foundation

You need durable strength across:

- Python
- Software engineering practices
- DSA and problem solving
- SQL and database internals
- OS and Linux fundamentals
- Networking and debugging
- Systems thinking
- Data platform reliability

### Vertical Depth

Your vertical is not generic AI and not low-latency trading systems.

Your vertical is:

`Trading AI/ML research data platform`

That means building systems that support:

- market data ingestion and normalization
- data quality and reconciliation
- point-in-time correct feature generation
- dataset versioning and reproducibility
- experiment tracking
- model evaluation and regression checks

This is a better fit than generic RAG or broad LLM application work because it combines:

- your platform background
- your data engineering background
- your AI/ML experience
- your finance and trading domain context

---

## Why Design 3 Exists

### What `design1.md` gets right

- It positions you clearly.
- It recognizes trading/finance domain knowledge as a differentiator.
- It connects your background to real target roles.
- It points toward platform depth, data quality, SQL, concurrency, and ML platform work.

### Where `design1.md` is weak

- It is too interview-shaped.
- It compresses too much into a short sprint.
- It assumes some foundations can be repaired quickly when they actually need repetition and depth.
- It does not make software engineering discipline heavy enough.
- It names good topics, but some of them are still not grounded enough in first principles.

### What `design2.md` gets right

- It is much stronger on fundamentals.
- It correctly emphasizes Python, testing, typing, design, databases, Linux, and systems design.
- It is closer to how strong engineers actually build depth.
- It pushes build-based learning rather than passive reading.

### Where `design2.md` is weak

- It is too broad for a 12-week plan.
- It is too generic for your target vertical.
- It gives too much room to topics that are useful but not urgent for your path.
- Its AI vertical is still too broad and too generic.

### Design 3 Decision

Design 3 keeps:

- the strong fundamentals from `design2.md`
- the role clarity and finance context from `design1.md`

Design 3 removes:

- overly broad AI topics
- too much company-specific interview prep in the main body
- unrealistic scope for a strict 12-week window

---

## Operating Principles

### Principle 1: Foundation Before Differentiation

Your differentiator only matters if the foundation is strong enough to support it.

Python, software engineering, databases, systems, and platform reliability come before vertical polish.

### Principle 2: Build, Measure, Explain

Each phase must produce:

- something you built
- something you measured
- something you can explain under pressure

### Principle 3: One Thin Vertical Slice Beats Ten Broad Topics

Do not try to "cover AI/ML" broadly.

Build one narrow end-to-end slice from raw market data to evaluated model output and make it correct, reproducible, and explainable.

### Principle 4: Strong Means Three Levels

For each topic, the bar is:

- `Understand`: you can follow the concept and reason about it.
- `Can implement`: you can build a small working version.
- `Can explain under pressure`: you can explain tradeoffs, failure modes, and when not to use it.

### Principle 5: Protect the Time Budget

This roadmap only works if the load stays realistic.

- weekday hour = focused drill or focused implementation
- weekend block = build, testing, benchmarking, or write-up
- if overloaded, reduce breadth rather than rushing

---

## Anti-Goals

This plan is not optimized for:

- low-latency execution systems
- HFT network/kernel/C++ specialization
- broad agent frameworks
- generic RAG platform work
- full-stack product engineering
- advanced quant research math
- deep learning research depth

Those can come later. They should not dilute the current foundation build.

---

## Weekly Rhythm

Use the same rhythm every week.

### Monday to Thursday

- `20 min`: review notes from the previous session
- `25 min`: focused drill on one concept
- `15 min`: write a short explanation or benchmark note

### Friday

- consolidate the week's notes
- fix misunderstandings
- write down 3 things you can now explain clearly

### Weekend

- `2-4 hours total`
- complete one build increment
- add tests
- write a short artifact or README note

If a week slips, do not add more topics. Carry unfinished work into the next week.

---

## 12-Week Overview

| Weeks | Theme | Primary Outcome |
|------|-------|-----------------|
| 1-4 | Python + engineering discipline | Tested `stdlib-first` data toolkit |
| 5-6 | Core CS + databases | Data-structure + query-performance lab |
| 7-8 | Systems + platform foundations | Reliable ingestion prototype |
| 9-10 | Trading data + ML foundations | Canonical data model + feature generation spec |
| 11-12 | Vertical capstone | End-to-end trading AI/ML platform slice |

---

## Foundation Quality Gate

Do not accelerate into the vertical just because the calendar says Week 9.

Before going deep, you should be at least `Can implement` in these foundation areas:

- Python fluency and internals
- software engineering discipline
- DSA and problem solving
- SQL and database internals
- systems, Linux, and networking basics
- data platform reliability
- systems design and tradeoff reasoning

If one of these is still weak, spend another week reinforcing it and shrink the vertical scope instead.

This matters more than sticking to the exact week count.

---

## Implementation Assets

The roadmap is phase-based, but the working materials should be topic-based.

That is why the notebook implementation is organized under `notebooks/` by foundation domain:

- Python foundations
- software engineering foundations
- DSA and problem-solving foundations
- SQL and database foundations
- systems, Linux, and networking foundations
- data platform foundations
- systems design foundations
- trading data and ML foundations

This split is intentional.

Use the phases in this document to manage pacing and scope.

Use the notebooks to do the actual drills, build work, notes, and checkpoints.

---

## Recommended Working Sequence

Follow the implementation assets in this order:

1. `01_python_foundations`
2. `02_python_internals_and_performance`
3. `03_software_engineering_foundations`
4. `04_dsa_problem_solving_foundations`
5. `05_sql_database_foundations`
6. `06_systems_linux_networking_foundations`
7. `07_data_platform_foundations`
8. `08_systems_design_foundations`
9. `09_trading_data_ml_foundations`

This sequence is deliberate:

- Python fluency comes before Python internals.
- Python internals come before engineering discipline so performance and correctness discussions are not abstract.
- DSA and SQL/database reasoning come before systems/platform work.
- systems, networking, platform reliability, and design reasoning come before the trading vertical.

If a phase runs long, do not skip ahead just to preserve the calendar. Shrink the vertical first.

---

## Core Public Entities for the Vertical

These are the core conceptual interfaces for the finance/trading part of the roadmap. They should appear in your designs, code, tests, and portfolio artifacts.

### `Instrument`

Canonical instrument metadata.

Suggested fields:

- `instrument_id`
- `symbol`
- `venue`
- `asset_class`
- `currency`
- `tick_size`
- `lot_size`
- `effective_start`
- `effective_end`

### `Trade`

Executed market event.

Suggested fields:

- `source`
- `trade_id`
- `instrument_id`
- `event_time`
- `ingest_time`
- `price`
- `size`
- `conditions`

### `Quote`

Top-of-book or book-level quote state.

Suggested fields:

- `source`
- `instrument_id`
- `event_time`
- `ingest_time`
- `bid_price`
- `bid_size`
- `ask_price`
- `ask_size`

### `Bar`

Aggregated market data interval.

Suggested fields:

- `instrument_id`
- `bar_start`
- `bar_end`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `vwap`
- `adjustment_flag`

### `CorporateAction`

Instrument event that can affect historical comparability.

Suggested fields:

- `instrument_id`
- `action_type`
- `effective_date`
- `ratio`
- `cash_amount`
- `source`

### `DatasetSnapshot`

A reproducible training or evaluation dataset view.

Suggested fields:

- `snapshot_id`
- `as_of_time`
- `source_versions`
- `feature_view_version`
- `row_count`
- `schema_version`
- `creation_time`

### `FeatureView`

Definition of a point-in-time feature set.

Suggested fields:

- `feature_view_name`
- `version`
- `entity_keys`
- `lookback_window`
- `input_sources`
- `transformation_logic`
- `point_in_time_rule`

### `ExperimentRun`

Tracked model experiment.

Suggested fields:

- `run_id`
- `dataset_snapshot_id`
- `model_type`
- `parameters`
- `metrics`
- `code_version`
- `run_time`

### `ModelArtifact`

Versioned trained model output.

Suggested fields:

- `model_id`
- `run_id`
- `feature_schema_version`
- `training_window`
- `evaluation_summary`
- `artifact_path`

### `DataQualityReport`

Structured result of validation and reconciliation checks.

Suggested fields:

- `report_id`
- `run_id`
- `check_name`
- `severity`
- `status`
- `affected_scope`
- `details`
- `generated_time`

---

## Phase 1: Weeks 1-4

## Python + Engineering Discipline

### Why

This is the most important phase in the entire plan.

If Python remains shallow, every later topic becomes slower:

- debugging is slower
- implementation is clumsier
- code quality is weaker
- testing is avoided
- performance reasoning stays fuzzy

The target is to stop using Python as a scripting tool and start using it as an engineering language.

### Core Concepts

- Python idioms and standard library fluency
- strings, collections, iterators, generators, context managers
- execution model:
  - name binding
  - scope rules
  - modules and imports
- object model and data model methods
- equality, identity, hashing, and ordering
- mutability and copy semantics
- reference counting and garbage collection basics
- list, dict, and set internals
- exceptions and error design
- serialization and parsing with `csv`, `json`, `datetime`, and `re`
- `pathlib`, `collections`, `itertools`, `functools`, `dataclasses`, `typing`, `logging`
- packaging with `pyproject.toml`
- test structure with `pytest`
- linting and type checking
- debugging and profiling basics:
  - `timeit`
  - `cProfile`
  - reading simple benchmark output
- basic concurrency mental models:
  - when threads help
  - when processes help
  - why the GIL matters
  - concurrency is expanded with hands-on drills in Phase 3
- design principles at a practical level:
  - SOLID principles (practical, not academic)
  - composition over inheritance as default
  - dependency injection as a design concept (not a framework)
  - DRY, KISS, YAGNI as scope control tools

### Python Priority Areas

Python is not just one line item in the foundation.

Treat it as four parallel subdomains:

- language fluency:
  - idioms
  - standard library
  - clean data transformations
- runtime and internals:
  - list, dict, set behavior
  - object identity
  - mutability
  - reference counting
  - GC
- engineering usage:
  - package structure
  - tests
  - typing
  - logging
  - CLI design
  - design principles: SOLID, composition, dependency injection
- practical performance reasoning:
  - eager vs lazy evaluation
  - algorithmic cost
  - memory behavior
  - threads vs processes at a high level

### Weekday Drills

- rewrite common loop-heavy code with clearer Python idioms
- build small exercises around `Counter`, `defaultdict`, `deque`, and `heapq`
- compare eager vs lazy processing
- write one module using `pathlib`, `csv`, `json`, and `datetime`
- write one decorator and one context manager from scratch
- benchmark list lookup vs set lookup
- demonstrate shallow vs deep copy bugs
- reproduce mutable default argument and late-binding closure bugs
- compare identity vs equality and explain when hashing breaks
- add type hints to every small exercise
- write unit tests for every utility function
- profile one small script and write down the bottleneck
- take one small exercise and refactor it: extract a function, replace inheritance with composition, or inject a dependency

### Weekend Build

Build a tested `stdlib-first data toolkit`.

The toolkit should:

- read CSV and JSON
- validate schema at a basic level
- support lazy row processing
- log structured pipeline steps
- expose a CLI
- format output cleanly
- use custom exceptions
- include `pytest`, linting, and type checks

This build must avoid pandas and heavy external libraries. The point is to force fluency with Python fundamentals.

### Python Quality Gate

Do not leave Phase 1 until you can do most of the following without searching every step:

- explain identity vs equality
- explain mutability and copy behavior
- explain list, dict, and set behavior at a practical level
- explain how imports, modules, and package boundaries work
- use `pathlib`, `csv`, `json`, `collections`, `itertools`, `typing`, and `logging` comfortably
- write tests and type hints as part of normal implementation
- use `timeit` or `cProfile` to reason about performance
- explain when threads help, when processes help, and why the GIL matters

### Exit Criteria

You can:

- explain how list and dict behave internally at a practical level
- explain name binding, scope, and module-import behavior at a practical level
- explain the GIL without hand-waving
- choose between generator and list deliberately
- structure a small Python package cleanly
- write and run tests without friction
- add type hints and keep them consistent
- profile a small script and explain where time is going
- explain SOLID principles at a practical level with Python examples
- prefer composition over inheritance and explain why

### Proof of Work

- `stdlib-first` data toolkit
- test suite
- short benchmark note on collection and generator behavior
- short note on import/package boundaries and module structure
- short design note on package layout and error handling

---

## Phase 2: Weeks 5-6

## Core CS + Databases

### Why

This phase builds the decision-making layer behind data engineering and platform work.

You need to understand:

- why one data structure is better than another
- why one query plan is slow
- why one schema ages badly
- why time-series data modeling needs deliberate tradeoffs

### Core Concepts

- Big-O, amortized cost, and space complexity
- arrays, hash maps, heaps, queues, graphs
- BFS, DFS, topological sort, binary search, sliding window
- SQL execution order
- joins, window functions, CTEs
- `EXPLAIN ANALYZE`
- index behavior and composite key ordering
- MVCC
- transaction isolation basics
- WAL and crash recovery basics
- partitioning by date and symbol
- time-series data modeling
- normalization vs denormalization
- dimensional modeling basics:
  - star schema and snowflake schema
  - slowly changing dimensions (SCD Type 1 and Type 2)
  - when to normalize vs denormalize (decision framework, not just the terms)
  - data vault concepts at awareness level only

### Weekday Drills

- implement one core data structure from scratch
- solve one graph problem and explain the data structure choice
- write one query using window functions
- compare a query with and without the right index
- inspect an execution plan and identify the bottleneck
- model one time-series table for trades or quotes
- explain one isolation-level tradeoff in practical terms
- explain when partitioning helps and when it hurts
- model one dimension table with SCD Type 2 for instrument metadata (effective_start, effective_end)

### Weekend Build

Build a `query and data-structure lab`.

The lab should include:

- a few small data structure implementations or exercises
- a repeatable SQL benchmark setup
- sample time-series tables
- indexed and non-indexed query comparisons
- short notes on query-plan differences

The build is not a full database engine. It is a measurement and reasoning lab.

### Exit Criteria

You can:

- choose an appropriate data structure and justify it
- explain time and space tradeoffs
- write solid SQL without relying on trial and error
- read an execution plan and identify the dominant issue
- explain MVCC and why it matters in concurrent systems
- explain transaction isolation choices at a practical level
- model time-series data with reasonable partition and index choices
- explain when to use star schema vs normalized schema and justify the choice
- explain SCD Type 2 and why it matters for historical correctness

### Proof of Work

- data-structure lab
- SQL benchmark notebook or notes
- query-plan comparison write-up
- time-series schema draft with rationale

### DSA Problem Bank

A minimum viable problem set covering the RED and YELLOW gaps. Attempt each from scratch without reference. Target time indicates readiness — if a problem takes more than 2x target, the underlying pattern needs more drill.

**Hash map:**
- Two Sum (LC 1) — 5 min
- Group Anagrams (LC 49) — 10 min

**Sliding window:**
- Longest Substring Without Repeating Characters (LC 3) — 10 min

**DFS:**
- Number of Islands (LC 200) — 15 min
- Max Depth of Binary Tree (LC 104) — 5 min
- Word Search (LC 79) — 15 min

**BFS:**
- Binary Tree Level Order Traversal (LC 102) — 10 min

**Topological sort:**
- Course Schedule (LC 207) — 15 min (directly relevant to DAG/pipeline work)

**Binary search:**
- Binary Search (LC 704) — 5 min
- Search in Rotated Sorted Array (LC 33) — 15 min

**Stack:**
- Valid Parentheses (LC 20) — 5 min

**Dynamic programming:**
- Climbing Stairs (LC 70) — 5 min
- Coin Change (LC 322) — 15 min
- House Robber (LC 198) — 10 min
- Longest Common Subsequence (LC 1143) — 15 min

**Heap:**
- Find Median from Data Stream (LC 295) — 15 min
- Merge Intervals (LC 56) — 10 min

### Pattern Templates

DFS (iterative):
```python
def dfs(graph, start):
    visited = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                stack.append(neighbor)
    return visited
```

BFS:
```python
from collections import deque
def bfs(graph, start):
    visited = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited
```

DP pattern:
```
1. Define state: dp[i] = answer for subproblem i
2. Find recurrence: dp[i] = f(dp[i-1], dp[i-2], ...)
3. Base case: dp[0] = ...
4. Build bottom-up (iterate) or top-down (memoize)
5. Answer = dp[n]
```

---

## Phase 3: Weeks 7-8

## Systems + Platform Foundations

### Why

Platform engineers fail when they treat the operating system, the network, and data pipelines as black boxes.

This phase makes the stack more concrete:

- how processes behave
- how memory and file descriptors fail
- what actually happens in basic network flows
- how reliable data pipelines are designed

### Core Concepts

- process vs thread vs coroutine
- virtual memory, heap, stack, page faults
- file descriptors and common leak patterns
- buffered I/O and flush semantics
- shell and Linux debugging tools:
  - `ps`, `top` or `htop`, `lsof`, `ss`, `strace`, `curl`
- concurrency (hands-on, building on Phase 1 mental models):
  - threading: locks, RLock, race conditions, deadlock prevention
  - multiprocessing: Pool, shared memory, IPC overhead
  - asyncio: event loop, coroutines, gather
  - producer-consumer pattern with `queue.Queue`
  - GIL interaction with each concurrency model
  - lock ordering as a deadlock prevention strategy
- networking fundamentals:
  - DNS resolution: what happens, caching, TTL
  - TCP: three-way handshake, connection pooling, keep-alive
  - HTTP request lifecycle: from DNS to response
  - TLS handshake at a conceptual level
  - common failure modes: connection refused, timeout, DNS failure, certificate expiry
- retries, backoff, timeouts
- idempotency
- data contracts, lineage, and backfills
- schema evolution
- CDC concepts
- batch vs stream tradeoffs
- observability basics
- SLIs, SLOs, and operational signals
- systems design fundamentals:
  - requirements and constraints
  - rough estimation
  - interface and data-model-first thinking
  - failure modes and tradeoff reasoning

### Weekday Drills

- inspect open files and describe failure modes
- reproduce a simple retry problem and add backoff
- trace a request from DNS to HTTP response using `curl -v` and `ss`
- write a race condition, then fix it with a lock
- implement producer-consumer with `queue.Queue`
- compare threading vs asyncio vs sequential for I/O-bound work (e.g., 20 mock fetches)
- diagnose a simulated network failure (DNS, TCP, TLS, or HTTP level) and explain where it broke
- define idempotency keys for an ingestion scenario
- write one small design sketch with inputs, outputs, failure modes, and metrics
- design a schema-change handling rule
- write 3 operational metrics for a pipeline

### Weekend Build

Build a thin `reliable ingestion pipeline`.

The prototype should:

- read from a mock source
- validate records
- reject or quarantine bad records
- support reruns safely
- track duplicates
- emit simple run metrics
- write a structured data quality summary

This is a thin slice, not a full framework.

If Phase 3 takes an extra week, that is acceptable. Do not rush concurrency, networking, or rerun/idempotency concepts just to keep the vertical schedule unchanged.

### Exit Criteria

You can:

- explain common process, memory, and file-descriptor failures
- explain the difference between event time and ingestion time
- design a rerunnable ingestion job
- explain idempotency, retries, and dead-letter or quarantine patterns
- sketch a small system with defensible boundaries and tradeoffs
- define useful operational metrics for data pipelines
- explain when to use threads, processes, or asyncio and why
- explain how the GIL interacts with each concurrency model
- implement a producer-consumer pipeline
- trace a network request from DNS to HTTP response and explain each layer
- diagnose which network layer failed given symptoms

### Proof of Work

- ingestion prototype
- validation and rerun design note
- small debugging workbook
- small systems design note with failure-mode analysis
- short metrics and runbook draft

---

## Phase 4: Weeks 9-10

## Trading Data + ML Foundations

### Why

This is where the vertical starts, but it still stays foundational.

The goal is not to build a fancy model. The goal is to understand the data and control the correctness of the pipeline around it.

Most weak finance/ML projects fail on:

- ambiguous instrument identity
- bad time handling
- leakage
- mixing corrected and uncorrected data
- ignoring corporate actions
- irreproducible datasets

### Core Concepts

- market-data entity design:
  - instruments
  - trades
  - quotes
  - bars
  - corporate actions
- symbology and canonical identifiers
- venue calendars and session boundaries
- event time vs processing time vs as-of time
- late and corrected records
- point-in-time correctness
- leakage prevention
- rolling windows and lookbacks
- train, validation, and test splits by time
- basic statistics required for feature work:
  - mean
  - variance
  - z-score
  - correlation
  - drift intuition
- experiment reproducibility
- dataset and feature versioning

### Weekday Drills

- define a canonical schema for one market-data domain
- map two mock vendor formats into one internal model
- write rules for session handling and timezone normalization
- write examples of leakage and how to prevent them
- define point-in-time joins in plain English
- design 5 simple features with explicit lookback windows
- compare random split vs time split and explain why random split is wrong here

### Weekend Build

Produce two artifacts:

- a `canonical trading data model`
- a `feature generation spec`

The feature spec should define:

- entity keys
- source tables
- lookback windows
- allowed timestamps
- leakage rules
- missing-data rules
- reproducibility expectations

### Exit Criteria

You can:

- explain why time handling is the core correctness issue in trading data
- normalize two vendor schemas into one internal model
- describe point-in-time correctness clearly
- explain why leakage destroys model credibility
- define a feature view that can be reproduced later

### Proof of Work

- canonical schema document
- vendor mapping document
- feature generation spec
- point-in-time and leakage test cases

---

## Phase 5: Weeks 11-12

## Vertical Capstone

### Why

This phase turns the previous work into one coherent slice that proves you can support trading-oriented AI/ML workflows with strong engineering discipline.

This capstone is deliberately narrow. It should be correct, testable, reproducible, and explainable.

### Core Concepts

- raw to canonical data flow
- quality gates and reconciliation
- partitioned storage
- point-in-time feature generation
- dataset snapshotting
- experiment tracking
- evaluation and regression checks
- reproducibility and lineage

### Exact Capstone Flow

The capstone must implement this flow:

`raw vendor data -> canonical normalized data -> quality and reconciliation checks -> partitioned storage -> point-in-time features -> dataset snapshot -> experiment run -> evaluation report`

### Weekend Build

Build one thin end-to-end slice that:

- ingests two mock market-data sources
- normalizes them into the canonical model
- runs schema, completeness, and reasonableness checks
- performs cross-source reconciliation
- persists partitioned canonical data
- generates point-in-time features
- creates a dataset snapshot
- runs one simple experiment
- records experiment metadata
- produces an evaluation report

Optional extension only if ahead of schedule:

- batch inference output
- simple monitoring summary

### Exit Criteria

You can:

- explain the data flow end to end
- trace a model result back to dataset and source inputs
- show how late, duplicate, or bad data is handled
- explain how reproducibility is preserved
- show where quality regressions would be detected

### Proof of Work

- capstone repository
- architecture note
- evaluation report
- experiment metadata record
- short demo walkthrough

---

## Test Plan

The roadmap is only valid if each phase has explicit verification.

### Python

Test for:

- mutability traps
- shallow vs deep copy behavior
- iterator vs generator behavior
- type-check correctness
- packaging and import sanity
- logging behavior
- simple performance reasoning backed by measurements

### Engineering

Test for:

- unit tests on core utilities
- lint and format compliance
- type checks
- refactoring safety
- error-path behavior

### DSA + Databases

Test for:

- correctness of implemented structures or algorithms
- time and space explanation
- query correctness
- `EXPLAIN ANALYZE` interpretation
- index selection effects
- schema design rationale

### Systems + Platform

Test for:

- rerun safety
- duplicate handling
- bad-record handling
- late-record handling
- retry behavior
- file-descriptor awareness
- memory-pressure awareness
- basic network-debug scenario reasoning

### Trading + ML

Test for:

- session boundary handling
- timezone normalization
- corrected record handling
- corporate-action awareness
- point-in-time integrity
- leakage prevention
- reproducibility of dataset snapshots
- experiment traceability
- drift or regression visibility

---

## Suggested Portfolio Artifacts

By the end of the 12 weeks, the target portfolio should contain:

- `stdlib-first-data-toolkit`
- `query-and-data-structure-lab`
- `reliable-ingestion-prototype`
- `canonical-trading-data-model`
- `trading-ml-platform-slice`

These do not all need to be large repositories. Some can be compact projects plus strong write-ups. The important thing is that each artifact proves a specific capability.

---

## What to De-Scope

Do not expand this plan with:

- generic agent frameworks
- broad LLM product work
- RAG depth unrelated to the target vertical
- advanced distributed systems rabbit holes
- low-latency/HFT internals
- broad cloud certification-style study

If extra time appears, deepen the capstone instead of widening the syllabus.

---

## Appendix: Interview Use

Interview preparation should be a side effect of this roadmap, not the main structure.

### Phase-to-Interview Readiness

| Phase | What It Unlocks |
|-------|----------------|
| Phase 1 (Python + SE) | Python internals questions, coding fluency, clean code discussion |
| Phase 2 (CS + DB) | DSA coding rounds, SQL rounds, data modeling questions |
| Phase 3 (Systems + Platform) | Systems design rounds, debugging scenarios, concurrency questions |
| Phase 4 (Trading + ML) | Domain-specific questions, data quality discussion, feature engineering |
| Phase 5 (Capstone) | End-to-end system walkthrough, portfolio presentation |

### Behavioral Minimum

Prepare and practice out loud:

- **"Tell me about yourself" (2 min):** Map your T-shape to the target role. Lead with "AI Data Platform Engineer," cover platform impact at each role, close with trading domain as differentiator. Practice weekly until natural.

- **3 STAR stories (under 2 min each):**
  - a data quality issue you found and fixed (draw from Tencent migrations)
  - a system you built that other teams depended on (database auditor at Tencent, or GraphRAG at GovTech)
  - working under pressure (production support or trading desk)

- **Data debugging scenarios (explain reasoning out loud):**
  - "15 tickers show zero prices since yesterday"
  - "Pipeline normally takes 10 min, running 2 hours"
  - "Researcher says volume data looks wrong since Tuesday"

### Communication Practice Rule

At the end of each Friday consolidation, pick one concept from that week and explain it out loud for 2 minutes as if in an interview. This builds the "explain under pressure" muscle from Principle 4 without adding a separate prep phase.

### Positioning

By the end of this plan, you should be able to tell a coherent story:

- you strengthened Python and engineering fundamentals
- you built stronger database and systems reasoning
- you understand data-platform reliability
- you can model trading data correctly
- you can build a reproducible AI/ML data workflow in a finance context

That is a better long-term positioning story than a purely interview-shaped sprint.

---

## Final Notes

This roadmap is a launchpad, not an endpoint.

If completed seriously, it should leave you with:

- stronger day-to-day engineering fundamentals
- cleaner Python and better software habits
- better systems and database intuition
- a credible trading AI/ML platform narrative
- one vertical slice that is specific enough to be defensible

The correct way to use this plan is not to "finish topics."

The correct way is to finish artifacts, tests, explanations, and mental models.
