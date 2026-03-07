# Project 2: Enterprise Knowledge Intelligence Platform (GraphRAG)

## What This Is
A system that ingests enterprise metadata (database schemas, dbt models, dashboards, documentation) into a knowledge graph, indexes document chunks as embeddings, and provides a natural language query interface combining graph traversal with vector search for grounded, explainable answers.

## Career Relevance
- **AI Engineering:** RAG is the most common production LLM pattern — building one from scratch shows deep understanding
- **ML Engineering:** Embedding models, vector similarity search, reranking, and evaluation (RAGAs) are core ML skills
- **Data Engineering:** Metadata ingestion, graph modeling, and hybrid retrieval demonstrate advanced data system design
- The LLM provider pattern (Ollama/Anthropic/OpenAI swappable via env var) shows production ML system design

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Knowledge Graph | Memgraph | Open-source, Cypher-compatible, in-memory. `neo4j` Python driver connects via Bolt. |
| Vector Store | pgvector (`pgvector/pgvector:pg16`) | Embedding storage + approximate nearest neighbor search |
| LLM | Provider pattern (see Master Plan) | Ollama default, Anthropic/OpenAI via env var |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) | Local embedding generation, 384 dimensions |
| Backend | FastAPI | REST + WebSocket |
| Frontend | Next.js | Query UI + graph visualization |
| Graph algorithms | MAGE (Memgraph) | PageRank, community detection |
| Evaluation | RAGAs | Faithfulness, relevancy, context precision/recall |

### Memgraph-Specific Notes
- No built-in vector indexes — all vector search goes through pgvector
- Use `localDateTime()` not `datetime()` for timestamps in Cypher
- `neo4j` Python driver connects via Bolt protocol natively — no Memgraph-specific driver needed
- Constraint syntax: `CREATE CONSTRAINT ON (n:Label) ASSERT n.prop IS UNIQUE`
- Memgraph does NOT support multi-property unique constraints natively — enforce composite uniqueness at application level via MERGE with all properties

## Folder Structure

```
knowledge-platform/
├── docker-compose.yml          # app, memgraph, postgres (pgvector), frontend
├── pyproject.toml
├── .env.example
├── Makefile
├── README.md
├── src/
│   ├── config.py
│   ├── llm/                    # Provider pattern: base, ollama, anthropic, openai, factory
│   ├── models/
│   ├── ingestion/              # One ingestor per source type
│   ├── graph/                  # Memgraph client, graph builder, Cypher queries
│   ├── embeddings/             # Chunker, embedder, vector store operations
│   ├── retrieval/              # Vector, graph, hybrid, reranker
│   ├── reasoning/              # Query engine, prompts, explainer
│   ├── evaluation/             # RAGAs eval, golden test sets, tracker
│   ├── api/
│   └── db/
├── frontend/
│   ├── app/                    # Query page, graph explorer
│   └── components/             # QueryBar, GraphViewer, ReasoningPath, ResultCard
├── simulation/
│   ├── seed.py                 # Populate graph with sample enterprise metadata
│   ├── simulator.py            # Continuously add/modify metadata
│   ├── sample_data/            # Sample dbt manifest, markdown docs, dashboard metadata
│   └── README.md
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/                   # Golden QA set, RAGAs runner
└── k8s/
```

## Graph Model

### Node Types
- **Database** — name, type, host, environment
- **Schema** — name, database
- **Table** — name, schema, database, description, row_count, last_updated
- **Column** — name, table (FQN), data_type, nullable, description
- **DbtModel** — name, path, materialization, description, tags
- **Dashboard** — name, platform, url, owner
- **Metric** — name, definition, formula, owner
- **Owner** — name, email, team
- **Document** — title, source, url, chunk_count
- **DocumentChunk** — content, embedding_id, chunk_index

### Relationships
- Table → Schema → Database (BELONGS_TO)
- Column → Table (BELONGS_TO)
- Table → Table (DEPENDS_ON — data lineage)
- DbtModel → Table (SOURCES), DbtModel → DbtModel (REFS), DbtModel → Table (MATERIALIZES)
- Dashboard → Table (USES), Dashboard → Metric (DISPLAYS)
- Metric → Table (DERIVED_FROM)
- Table/Dashboard → Owner (OWNED_BY)
- DocumentChunk → Document (PART_OF), DocumentChunk → Table (DESCRIBES)

## Data Models

### RetrievalResult
- `content`, `source` ("vector" / "graph"), `score`, `metadata` (node_id, node_type, relationship), `reasoning_path`

### QueryResponse
- `answer`, `confidence` (0.0-0.95, never 1.0), `sources` (top results with previews), `reasoning_path` (ordered steps), `cypher_used` (optional)

### EvalResult
- `question`, `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`

## Core Logic

### Ingestion (`src/ingestion/`)
- **SchemaIngestor** — asyncpg to read `information_schema`. Creates Database → Schema → Table → Column hierarchy. `pg_class.reltuples` for row count estimates.
- **DbtIngestor** — Parses `manifest.json`. Creates DbtModel nodes with SOURCES/REFS/MATERIALIZES edges.
- **DashboardIngestor** — Ingests from Tableau API or mock JSON. Creates Dashboard nodes + USES edges.
- **DocsIngestor** — Reads markdown files, chunks them, embeds, stores in pgvector. Creates Document/DocumentChunk nodes with DESCRIBES edges.

### Embeddings (`src/embeddings/`)
- **Chunker** — Recursive character splitter. Configurable chunk size (default 512 chars), overlap (default 50 chars).
- **Embedder** — Wraps Sentence Transformers model. Input: text → output: float[384]. Batch support for efficiency.
- **VectorStore** — pgvector table operations: insert with metadata, cosine similarity search with top-k, delete by ID.

### Retrieval (`src/retrieval/`)
- **VectorRetriever** — Embed query string, run pgvector ANN search, return top-k RetrievalResults.
- **GraphRetriever** — Three modes: (1) direct Cypher text matching (`toLower` + `CONTAINS`), (2) N-hop expansion from a node, (3) lineage queries (upstream/downstream with depth control).
- **HybridRetriever** — Orchestrates: vector search top-k → graph expansion from top 5 vector hits → direct graph search → merge/deduplicate → apply configurable vector/graph weights → rerank.
- **Reranker** — Cross-encoder reranking or LLM-based reranking of merged results.

### Reasoning (`src/reasoning/`)
- **QueryEngine** — Main flow: (1) classify query intent via LLM (lineage/metadata/definition/change/general), (2) run hybrid retrieval, (3) assemble numbered context, (4) generate answer via LLM with citation prompt, (5) estimate confidence (higher when vector+graph agree), (6) return QueryResponse.
- System prompt enforces: answer only from context, cite [Source N], describe lineage step-by-step, note conflicts, never speculate.

### Evaluation (`src/evaluation/`)
- Golden test set: JSON with questions, ground truth answers, expected context keywords
- RAGAs: faithfulness, answer relevancy, context precision, context recall
- Tracker: stores eval history, detects regressions over time

## Simulation

### seed.py
- 3 databases, 15 schemas, 80+ tables, 500+ columns with realistic names
- 20 dbt models with lineage (refs, sources, materializations)
- 10 dashboards, 15 metrics, 8 owners across 4 teams
- 30 markdown doc chunks describing business logic (revenue calculation, customer segmentation, etc.)

### simulator.py
- Periodically add new tables, modify descriptions, add new dbt models
- Simulate a new data source onboarding (creates multiple nodes/edges at once)
- Tests incremental ingestion

### sample_data/
- `dbt_manifest.json` — realistic manifest with 20 models
- `docs/` — 10 markdown files on business metrics and processes
- `dashboards.json` — mock Tableau metadata

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/query` | NL question → QueryResponse |
| GET | `/api/v1/graph/node/{id}` | Node details + neighbors |
| GET | `/api/v1/graph/lineage/{table}` | Upstream/downstream |
| GET | `/api/v1/graph/search` | Search nodes by name/description |
| POST | `/api/v1/ingestion/run` | Trigger ingestion for a source type |
| POST | `/api/v1/eval/run` | Run evaluation suite |
| GET | `/api/v1/eval/results` | Evaluation history |
| GET | `/health` | Health check |

## Docker Compose Services
- `app` — FastAPI backend
- `memgraph` — `memgraph/memgraph-platform:latest` (Bolt 7687, Lab UI 3000)
- `postgres` — `pgvector/pgvector:pg16` with pgvector extension
- `frontend` — Next.js

## Implementation Phases

### Phase 1: Metadata Ingestion
SchemaIngestor + DbtIngestor, Memgraph constraints/indexes, seed.py. **Success:** browse graph in Memgraph Lab (http://localhost:3000).

### Phase 2: Graph Enrichment
DashboardIngestor, DocsIngestor, Owner nodes. **Success:** 5+ node types, 8+ relationship types.

### Phase 3: Vector Indexing
Chunker, embedder, pgvector store, VectorRetriever. **Success:** query returns relevant doc chunks.

### Phase 4: Hybrid Retrieval
GraphRetriever, HybridRetriever, reranker. **Success:** hybrid outperforms vector-only on golden test set.

### Phase 5: Reasoning + Evaluation
QueryEngine with LLM provider pattern, RAGAs pipeline. **Success:** end-to-end NL → grounded answer, 80%+ faithfulness.

### Phase 6: Frontend + Simulation
Next.js UI with graph visualization, simulator.py. **Success:** full demo with live data changes.

## Performance Targets
- End-to-end query: < 3 seconds
- Graph traversal (Cypher): < 200ms
- Vector search (pgvector): < 100ms
- Precision@5: > 0.7
- Faithfulness (RAGAs): > 0.8