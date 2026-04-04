# Foundational Skills Development Plan

## Context

4+ years across data engineering, AI/ML, infrastructure, and solution development.
Background: Manufacturing Engineering diploma → CS degree → FX trading → tech.
Current role: Data Engineer at GovTech (GraphRAG, pipelines, GenAI full-stack).

Core frustration: breadth without depth. Can "do things" but gaps in fundamentals
cause friction — e.g. manually formatting `1234` → `1,234` with enumerate when
`f"{n:,}"` exists. This isn't about intelligence — it's about not having built
the muscle memory of a language's idioms because the career has been a sprint
across many tools rather than a deep dive into any one.

---

## Gap Analysis (from resume + self-assessment)

### What's strong
- Breadth of exposure: cloud (AWS/GCP/Azure), databases (6+ systems), AI/ML pipeline work
- Can build end-to-end: frontend to backend to infra to ML
- Real production experience: migrations, monitoring, deployments
- Non-trivial AI work: fine-tuning, GraphRAG, evaluation pipelines
- Soft skills: mentoring, vendor management, cross-team coordination

### What's missing or shallow

| Gap | Evidence | Impact |
|-----|----------|--------|
| Python mastery | f-string gap, "scripting" level comfort | Slows everything — Python is your primary language |
| Data structures & algorithms | Algorithmic thinking exists but implementation is ad-hoc | Struggles in interviews, writes suboptimal code |
| Software engineering practices | No testing mentioned anywhere on resume | Code is fragile, hard to maintain, hard to collaborate on |
| Systems design depth | Has done architecture but likely pattern-matching not principled | Can't confidently design systems from first principles |
| Networking & protocols | Used FIX protocol in trading, but no web networking depth | Gaps show up in debugging, security, API design |
| Database internals | Used 6+ databases but likely at the query level | Can't optimize, can't choose the right DB for the right reason |
| OS & Linux internals | Uses Linux daily but likely surface-level | Debugging production issues hits a wall |
| Clean code & design patterns | No mention of SOLID, patterns, refactoring | Code works but isn't maintainable or extensible |

---

## Learning Architecture

Structure: 8 modules. Each module has:
- **Concepts**: what to understand (theory)
- **Exercises**: small, focused practice (drills)
- **Project**: one substantial build that forces applied learning
- **Checkpoint**: how to know you've "got it"

Target: work through 1 module every 2-3 weeks. Total ~4-6 months for foundations.

---

## Module 1: Python Mastery

**Why this is first**: Python is your daily driver. Every minute saved here
compounds across everything else you do. This is not "learn Python" — this is
"stop fighting the language and start thinking in it."

### Concepts
- Built-in types deep dive: `str`, `int`, `float`, `list`, `dict`, `set`, `tuple`
  - String formatting: f-strings, format specs (`f"{n:,}"`, `f"{x:.2f}"`, `f"{s:<20}"`)
  - Dict comprehensions, `defaultdict`, `Counter`, `OrderedDict`
  - Set operations: union, intersection, difference, symmetric_difference
  - Tuple unpacking, named tuples, `dataclasses`
- Iteration patterns
  - `enumerate`, `zip`, `itertools` (chain, product, combinations, groupby)
  - Generator expressions vs list comprehensions (memory implications)
  - `yield` and generator functions — when and why
- Functions as first-class objects
  - `map`, `filter`, `reduce` vs comprehensions
  - `functools`: `partial`, `lru_cache`, `wraps`
  - Closures and decorators — write your own
  - `*args`, `**kwargs`, keyword-only arguments
- Error handling patterns
  - Exception hierarchy, custom exceptions
  - Context managers (`with` statement), writing your own with `__enter__`/`__exit__`
  - `try/except/else/finally` flow
- Python object model
  - `__init__`, `__repr__`, `__str__`, `__eq__`, `__hash__`
  - `@property`, `@staticmethod`, `@classmethod`
  - Inheritance vs composition (prefer composition)
  - Protocols and duck typing, `abc.ABC`
- Standard library you should know cold
  - `pathlib` (not `os.path`), `collections`, `itertools`, `functools`
  - `json`, `csv`, `re`, `datetime`, `typing`
  - `subprocess`, `shutil`, `argparse`
  - `logging` (not `print` debugging)
- Package & environment management
  - `venv`, `pip`, `pyproject.toml`
  - Understand `__init__.py`, relative imports, package structure

### Exercises
```
exercises/python_mastery/
├── 01_string_formatting.py      # Format numbers, dates, tables using f-strings
├── 02_collections_workout.py    # Counter, defaultdict, deque problems
├── 03_comprehensions.py         # Convert loops to comprehensions and back
├── 04_generators.py             # Build a lazy pipeline (read → filter → transform → output)
├── 05_decorators.py             # Write: timer, retry, memoize, validate_args decorators
├── 06_context_managers.py       # Write: file handler, db connection, timer context managers
├── 07_dataclasses.py            # Model real domain objects, implement __eq__ and __hash__
└── 08_stdlib_challenges.py      # Solve 10 problems using only stdlib (no pip installs)
```

### Project: CLI Data Toolkit
Build a command-line tool that:
- Reads CSV/JSON files using `pathlib` and stdlib
- Transforms data using generators (lazy processing)
- Outputs formatted tables using f-strings
- Has proper error handling with custom exceptions
- Uses `argparse` for CLI interface
- Has `logging` instead of print statements
- Packaged properly with `pyproject.toml`

**Constraint**: no pandas, no external libraries. Force yourself to use stdlib.

### Checkpoint
- Can you format any number/string/date with f-strings without looking it up?
- Can you write a decorator from scratch?
- Can you explain the difference between `__str__` and `__repr__`?
- Can you structure a Python package with proper imports?

---

## Module 2: Data Structures & Algorithms

**Why**: not for leetcode grinding — for building intuition about why code is
slow and how to think about problems structurally. Your enumerate approach to
number formatting shows you can think algorithmically; now formalize it.

### Concepts
- Complexity analysis
  - Big-O, Big-Omega, Big-Theta — what they actually mean
  - Amortized analysis (why `list.append` is O(1))
  - Space complexity — often more important than time in data engineering
- Core data structures (implement each from scratch in Python)
  - Arrays and dynamic arrays (understand how Python `list` works internally)
  - Linked lists (singly, doubly) — understand when they beat arrays
  - Hash tables — how Python `dict` works under the hood (open addressing)
  - Stacks and queues — using `collections.deque`
  - Trees: binary trees, BSTs, tries
  - Heaps / priority queues — `heapq` module
  - Graphs: adjacency list vs matrix, when to use which
- Core algorithms
  - Sorting: understand quicksort, mergesort, timsort (Python's sort)
  - Searching: binary search, two pointers, sliding window
  - Graph: BFS, DFS, topological sort, Dijkstra's
  - Dynamic programming: memoization vs tabulation, recognize the pattern
  - String algorithms: pattern matching, string hashing
- Data structure selection
  - "Which structure for which problem" decision framework
  - Trade-offs: lookup speed vs insertion speed vs memory vs ordering

### Exercises
```
exercises/dsa/
├── 01_implement_hashmap.py       # Build a hash map from scratch
├── 02_implement_lru_cache.py     # OrderedDict or doubly-linked list + dict
├── 03_graph_traversal.py         # BFS/DFS on adjacency list
├── 04_topological_sort.py        # Critical for understanding DAGs (Airflow!)
├── 05_binary_search_variants.py  # Lower bound, upper bound, rotated array
├── 06_sliding_window.py          # Max subarray, min window substring
├── 07_tree_operations.py         # Serialize/deserialize, LCA, traversals
└── 08_dp_patterns.py             # Climb stairs → knapsack → LCS progression
```

### Project: DAG Task Scheduler
Build a simple task scheduler that:
- Takes task definitions with dependencies (like a mini-Airflow)
- Performs topological sort to determine execution order
- Detects circular dependencies
- Supports parallel execution of independent tasks using `concurrent.futures`
- Tracks execution state using appropriate data structures
- Visualizes the DAG as text output

**Why this project**: directly maps to your Airflow/pipeline work but forces you
to understand the graph theory underneath.

### Checkpoint
- Can you analyze the time/space complexity of your own code?
- Can you implement a hash map and explain collision handling?
- Can you look at a problem and identify which data structure fits?

---

## Module 3: Software Engineering Practices

**Why**: your resume has zero mentions of testing. This is a red flag that
experienced engineers will notice. Testing isn't bureaucracy — it's how you
build confidence in code that handles production data.

### Concepts
- Testing pyramid
  - Unit tests: `pytest`, fixtures, parametrize, mocking
  - Integration tests: testing with real databases, APIs
  - End-to-end tests: when and when not to
  - Property-based testing: `hypothesis` library
- Test-driven development (TDD)
  - Red → Green → Refactor cycle
  - When TDD helps vs when it's overkill
- Code quality
  - Type hints: `typing` module, `mypy` for static analysis
  - Linting: `ruff` (replaces flake8, isort, black)
  - Pre-commit hooks
- Design principles
  - SOLID principles — practical not academic
  - DRY, KISS, YAGNI — when each applies
  - Composition over inheritance
  - Dependency injection (not the Java framework kind — the principle)
- Refactoring patterns
  - Extract function, extract class
  - Replace conditional with polymorphism
  - Introduce parameter object
- Git practices
  - Conventional commits
  - Branching strategies (trunk-based vs gitflow)
  - Interactive rebase, bisect for debugging
  - Writing good PR descriptions

### Exercises
```
exercises/engineering/
├── 01_pytest_basics/             # Write tests for Module 1's CLI toolkit
├── 02_tdd_kata/                  # Build a Roman numeral converter using TDD
├── 03_mocking/                   # Mock database calls, API calls, file system
├── 04_refactoring/               # Take messy code samples, refactor with tests as safety net
├── 05_type_hints/                # Add type hints to all previous code, run mypy
└── 06_property_testing/          # Use hypothesis to find edge cases in your code
```

### Project: Refactor + Test Your Module 1 & 2 Projects
Go back to your CLI toolkit and DAG scheduler:
- Add comprehensive test suites (aim for 80%+ coverage)
- Add type hints throughout
- Set up `ruff` and `mypy` in the project
- Set up pre-commit hooks
- Refactor any code smells the tests reveal
- Write a proper README with usage examples

### Checkpoint
- Can you write a test before writing the implementation?
- Can you mock external dependencies confidently?
- Does `mypy --strict` pass on your code?

---

## Module 4: Networking, Protocols & API Design

**Why**: you've used FIX protocol, built FastAPI backends, worked with Kafka
and REST APIs — but likely at the "make it work" level. Understanding the
layers underneath transforms your debugging ability.

### Concepts
- Network fundamentals
  - OSI model (practically: L3 IP, L4 TCP/UDP, L7 HTTP)
  - DNS resolution — what actually happens when you hit a URL
  - TCP handshake, connection pooling, keep-alive
  - TLS/SSL — how HTTPS works, certificate chains
- HTTP deep dive
  - Methods, status codes, headers — know them cold
  - Content negotiation, caching headers, CORS
  - HTTP/1.1 vs HTTP/2 vs HTTP/3
  - Cookies, sessions, JWT, OAuth2 flow
- API design
  - REST principles (not just "use GET and POST")
  - API versioning strategies
  - Pagination: cursor-based vs offset
  - Rate limiting, backoff, retry strategies
  - OpenAPI/Swagger spec
  - GraphQL basics — when it beats REST
- Async and concurrency in Python
  - `asyncio` event loop — how it works
  - `aiohttp`, `httpx` for async HTTP
  - `async/await` patterns
  - Difference between threading, multiprocessing, and asyncio
  - When to use each (I/O bound vs CPU bound)

### Exercises
```
exercises/networking/
├── 01_tcp_server.py              # Build a raw TCP echo server using `socket`
├── 02_http_from_scratch.py       # Parse raw HTTP request/response manually
├── 03_dns_resolver.py            # Build a simple DNS resolver
├── 04_api_design/                # Design and implement a RESTful API with FastAPI
│   ├── with_auth.py              # JWT auth flow
│   ├── with_pagination.py        # Cursor-based pagination
│   └── with_rate_limiting.py     # Implement rate limiting middleware
├── 05_async_scraper.py           # Async web scraper comparing sync vs async performance
└── 06_websocket_chat.py          # Real-time chat using websockets
```

### Project: API Gateway
Build a simple API gateway that:
- Accepts incoming HTTP requests
- Routes to different backend services based on path
- Implements rate limiting per client
- Adds JWT authentication
- Logs requests with proper structured logging
- Handles timeouts and retries with exponential backoff
- Uses `asyncio` for non-blocking I/O

### Checkpoint
- Can you explain what happens from DNS lookup to rendered page?
- Can you debug a 502 Bad Gateway without googling?
- Can you design a REST API that another engineer would find intuitive?

---

## Module 5: Database Internals & Data Modeling

**Why**: you've used 6+ databases. Now understand WHY they behave the way
they do, so you can choose the right one and optimize it.

### Concepts
- How databases work under the hood
  - B-trees and LSM-trees — the two fundamental storage structures
  - Write-ahead logging (WAL)
  - MVCC (how PostgreSQL handles concurrent reads/writes)
  - Query planning and execution — reading `EXPLAIN ANALYZE`
  - Index types: B-tree, hash, GiST, GIN, BRIN — when to use each
- Data modeling
  - Normalization (1NF through 3NF) — when to normalize, when to denormalize
  - Star schema and snowflake schema for analytics
  - Dimensional modeling (Kimball methodology)
  - Slowly changing dimensions (SCD Type 1, 2, 3)
  - Data vault modeling basics
- SQL mastery
  - Window functions: ROW_NUMBER, RANK, LAG, LEAD, running totals
  - CTEs and recursive CTEs
  - Lateral joins, array aggregation
  - Query optimization: index usage, join strategies, partitioning
  - Anti-patterns: N+1 queries, implicit type casting, missing indexes
- Distributed databases
  - CAP theorem — what it actually means in practice
  - Consistency models: strong, eventual, causal
  - Partitioning strategies: hash, range, composite
  - Replication: sync vs async, leader-follower vs multi-leader
  - Why you chose StarRocks vs PostgreSQL vs Cassandra (formalize your intuition)
- Graph databases
  - Property graph model (you already use Neo4j)
  - Cypher query optimization
  - When graphs beat relational: traversal-heavy queries

### Exercises
```
exercises/databases/
├── 01_explain_analyze/           # 10 slow queries — diagnose and fix using EXPLAIN
├── 02_window_functions.py        # Solve analytics problems using only window functions
├── 03_data_modeling/             # Design schemas for: e-commerce, social network, IoT
├── 04_index_lab/                 # Create indexes, measure performance before/after
├── 05_cdc_simulation.py          # Simulate change data capture from a source table
└── 06_graph_modeling/            # Model a real domain in Neo4j, optimize traversals
```

### Project: Mini Query Engine
Build a simplified query engine that:
- Reads CSV files as "tables"
- Supports: SELECT, WHERE, JOIN, GROUP BY, ORDER BY
- Implements a naive query planner (scan vs index lookup)
- Builds simple B-tree indexes on columns
- Shows an `EXPLAIN` output for each query
- Supports basic aggregations (COUNT, SUM, AVG)

### Checkpoint
- Can you read an `EXPLAIN ANALYZE` output and identify the bottleneck?
- Can you design a schema for a new business domain and justify your choices?
- Can you explain when to use PostgreSQL vs StarRocks vs Neo4j vs Redis?

---

## Module 6: Operating Systems & Linux Internals

**Why**: you manage Kubernetes clusters and production systems. Understanding
what's happening below the container abstraction makes you dramatically better
at debugging and performance work.

### Concepts
- Process management
  - Processes vs threads vs coroutines
  - Process lifecycle: fork, exec, wait
  - Signals: SIGTERM, SIGKILL, SIGHUP, SIGINT — what your containers receive
  - Process isolation: namespaces and cgroups (what Docker actually does)
- Memory
  - Virtual memory, page tables, page faults
  - Stack vs heap
  - Memory-mapped files (how databases use `mmap`)
  - OOM killer — why your pods get killed
- File systems
  - Inodes, file descriptors, hard links vs soft links
  - `/proc` and `/sys` — reading system state
  - File I/O: buffered vs direct, `fsync` semantics
- Networking (OS level)
  - Sockets, `epoll`, non-blocking I/O
  - `iptables`/`nftables` — how Kubernetes networking works under the hood
  - Network namespaces — how pod networking works
- Shell & scripting
  - Bash beyond basics: arrays, associative arrays, process substitution
  - `awk`, `sed`, `jq`, `xargs` — text processing power tools
  - `strace`, `ltrace` — tracing system calls
  - `perf`, `htop`, `iostat`, `vmstat` — performance analysis

### Exercises
```
exercises/linux/
├── 01_process_tree.sh            # Map the process tree of a running container
├── 02_namespace_lab.sh           # Create network/pid namespaces manually
├── 03_strace_debugging/          # Use strace to diagnose slow program, permission error
├── 04_proc_exploration.sh        # Read /proc to find memory usage, open files, etc
├── 05_shell_scripting/           # Rewrite 5 of your Python scripts in pure bash
└── 06_container_from_scratch.sh  # Build a "container" using namespaces + cgroups
```

### Project: Container Runtime (Simplified)
Build a minimal container runtime that:
- Creates a new PID and network namespace
- Sets up a cgroup with memory and CPU limits
- Mounts a root filesystem (use `alpine` rootfs)
- Runs a process inside the isolated environment
- Cleans up on exit

**Why this project**: you manage K8s clusters. Understanding what a container
actually is (just Linux primitives!) transforms your debugging ability.

### Checkpoint
- Can you explain why a pod was OOM-killed by reading kernel logs?
- Can you use `strace` to find why a process is hanging?
- Can you explain what `docker run` does at the syscall level?

---

## Module 7: Systems Design

**Why**: this is where everything comes together. You've done architecture
work (GraphRAG system, migration projects) but need to formalize the
thinking into a repeatable framework.

### Concepts
- Design framework
  - Requirements gathering: functional vs non-functional
  - Back-of-envelope estimation: QPS, storage, bandwidth
  - API design first, then data model, then architecture
  - Trade-off analysis: consistency vs availability, cost vs performance
- Core building blocks
  - Load balancers: L4 vs L7, algorithms
  - Caching: cache-aside, write-through, write-behind, cache invalidation
  - Message queues: Kafka vs RabbitMQ vs SQS — when to use each
  - CDNs, reverse proxies
  - Consistent hashing
  - Rate limiting algorithms: token bucket, sliding window
- Patterns
  - Microservices vs monolith — when each wins
  - Event-driven architecture, CQRS, event sourcing
  - Saga pattern for distributed transactions
  - Circuit breaker, bulkhead, retry patterns
  - Strangler fig pattern for migrations (you've done migrations!)
- Data-intensive systems
  - Batch vs stream processing — Lambda vs Kappa architecture
  - Exactly-once delivery and idempotency
  - Data lake, data warehouse, lakehouse — when each fits
  - Feature stores and ML serving architecture
- AI/ML system design (your differentiator)
  - RAG architecture patterns (you've built this!)
  - Model serving: online vs batch inference
  - A/B testing and shadow deployment for models
  - Feedback loops and data flywheel
  - Guardrails and evaluation in production

### Exercises
```
exercises/system_design/
├── 01_estimation.md              # Practice: estimate storage for 1B messages/day
├── 02_design_url_shortener.md    # Classic warmup
├── 03_design_data_pipeline.md    # Design Airflow-like system from scratch
├── 04_design_rag_system.md       # Design your GovTech system from first principles
├── 05_design_realtime_analytics.md # Design a system like your Tencent dashboards
└── 06_design_ml_platform.md      # Design an ML platform for model training + serving
```

### Project: System Design Document for Your Current Work
Take your GovTech GraphRAG system and write a proper design document:
- Requirements (functional and non-functional)
- Capacity estimation
- API design
- Data model
- High-level architecture with trade-off justifications
- Failure modes and mitigation
- Monitoring and alerting strategy
- Future scaling considerations

### Checkpoint
- Can you design a system on a whiteboard in 45 minutes?
- Can you identify 3 trade-offs in any architecture and justify your choice?
- Can you estimate storage/compute requirements from business requirements?

---

## Module 8: AI Engineering Fundamentals (Your Vertical)

**Why**: given your trajectory and current work, AI/data platform engineering
is your natural vertical. But you need to go deeper than "I used LangChain."

### Concepts
- LLM internals (not training — understanding)
  - Transformer architecture: attention, positional encoding, why it works
  - Tokenization: BPE, SentencePiece — why token count matters for cost/context
  - Inference optimization: KV caching, batching, quantization
  - Context window management: chunking strategies, retrieval augmentation
- Evaluation (your GovTech work touches this — go deeper)
  - Evaluation frameworks: task-specific vs general
  - Human eval vs automated eval — when each applies
  - Metrics: BLEU, ROUGE, BERTScore, faithfulness, relevance
  - Building evaluation datasets
  - Regression testing for AI systems
- RAG architecture (deepen what you already know)
  - Embedding models: choosing, fine-tuning, benchmarking
  - Vector databases: FAISS, Pinecone, pgvector — trade-offs
  - Chunking strategies: fixed, semantic, document-structure-aware
  - Retrieval: dense vs sparse vs hybrid
  - Re-ranking: cross-encoders, ColBERT
  - GraphRAG: your specialty — go deeper than anyone else
- Agent design patterns
  - ReAct, plan-and-execute, reflexion
  - Tool use and function calling
  - Multi-agent orchestration
  - Memory: short-term (context), long-term (vector store), working (scratchpad)
  - Guardrails and safety: content filtering, output validation
- MLOps and production AI
  - Model versioning and registry
  - Feature stores: online vs offline
  - Monitoring: data drift, concept drift, performance degradation
  - A/B testing and canary deployments for models
  - Cost optimization: model selection, caching, batching

### Exercises
```
exercises/ai_engineering/
├── 01_tokenizer_deep_dive.py     # Compare tokenizers, understand token economics
├── 02_embedding_benchmark.py     # Benchmark embedding models on your own dataset
├── 03_chunking_strategies.py     # Implement and compare 4 chunking approaches
├── 04_eval_framework.py          # Build a reusable evaluation harness
├── 05_agent_from_scratch.py      # Build a ReAct agent without LangChain
├── 06_rag_optimization.py        # Measure and optimize retrieval quality
└── 07_cost_calculator.py         # Build a tool that estimates LLM API costs
```

### Project: Production-Grade RAG Evaluation Suite
Build a comprehensive evaluation system for RAG pipelines:
- Automated test case generation from documents
- Multiple evaluation metrics (faithfulness, relevance, completeness)
- Regression detection: alert when quality drops
- Cost tracking per query
- Latency profiling per component (retrieval, generation, reranking)
- Dashboard showing quality trends over time
- Exportable reports for stakeholders

### Checkpoint
- Can you explain the transformer architecture without looking it up?
- Can you design a RAG system from scratch and justify every component choice?
- Can you build an evaluation pipeline that catches quality regressions?

---

## Execution Plan

### Phase 1: Core Language (Weeks 1-6)
- Module 1: Python Mastery (weeks 1-3)
- Module 2: DSA (weeks 4-6)

### Phase 2: Engineering Craft (Weeks 7-12)
- Module 3: Software Engineering Practices (weeks 7-9)
- Module 4: Networking & APIs (weeks 10-12)

### Phase 3: Systems Knowledge (Weeks 13-20)
- Module 5: Database Internals (weeks 13-15)
- Module 6: Linux Internals (weeks 16-18)
- Module 7: Systems Design (weeks 19-20)

### Phase 4: Vertical Depth (Weeks 21-26)
- Module 8: AI Engineering (weeks 21-26)

### Daily Practice Rhythm
- 30 min: exercises from current module (morning, before work)
- Work hours: actively apply what you're learning to your GovTech work
- 30 min: project work for current module (evening)
- Weekend: 2-3 hours on project, review week's learning

### How to Use This With an AI Coding Assistant
1. Open this file in VSCode
2. For each module, ask the assistant to scaffold the exercise files
3. Attempt each exercise yourself first — set a 30-min timer
4. If stuck, ask for hints not solutions
5. After completing, ask for code review focusing on idioms and patterns
6. For projects, start with your own design then iterate with feedback

### Tracking Progress
Create a `progress.md` in the same directory:
```markdown
## Module 1: Python Mastery
- [ ] Exercise 01: String formatting
- [ ] Exercise 02: Collections
- [ ] ...
- [ ] Project: CLI Data Toolkit
- [ ] Checkpoint: self-assessment passed
```

---

## Reading List

### Books (pick one per phase, don't hoard)
- Phase 1: "Fluent Python" by Luciano Ramalho (Python mastery bible)
- Phase 2: "Architecture Patterns with Python" by Percival & Gregory
- Phase 3: "Designing Data-Intensive Applications" by Martin Kleppmann
- Phase 4: "Building LLMs for Production" or similar current resource

### Resources
- Python: docs.python.org (the official docs are excellent, read them)
- DSA: neetcode.io roadmap (structured, not random grinding)
- Systems: github.com/donnemartin/system-design-primer
- AI: Anthropic's documentation, research papers from your current work
- Linux: Julia Evans' zines (wizardzines.com) — visual and practical

---

## Principles

1. **Build, don't just read.** Every concept should result in code you wrote.
2. **No tutorial hell.** If you're watching a video, you're procrastinating.
3. **Apply immediately.** Every module connects to your real work — use it.
4. **Depth over breadth.** You already have breadth. Go deep now.
5. **Test everything.** From Module 3 onward, nothing ships without tests.
6. **Explain to verify.** If you can't explain it simply, you don't know it.