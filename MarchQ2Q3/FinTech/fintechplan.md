# Project: AI-Powered Financial Intelligence Platform (v2)

## Architecture Decisions (Locked — Do Not Change Mid-Project)

| Decision | Choice | Rationale |
|---|---|---|
| Language | Python 3.13 | Broad library support, stable |
| Package manager | `uv` | Fast, deterministic, replaces pip + venv |
| LLM provider | Anthropic Claude (primary), OpenAI (embeddings only) | JD company uses Claude; OpenAI has best cheap embeddings |
| Vector DB | ChromaDB (local) → pgvector (prod) | Zero-setup locally, Postgres-native in prod |
| Structured DB | SQLite (local) → PostgreSQL (prod) | DuckDB for analytics queries locally |
| Query engine (local) | DuckDB over Parquet files | Replaces Athena locally, same SQL, zero cost |
| Query engine (prod) | AWS Athena | Swap in Phase 5 only |
| API framework | FastAPI | Industry standard for ML serving |
| Backtesting | vectorbt | Don't reinvent — extend it |
| Agent framework | LangGraph | JD names LangChain; LangGraph is its agent layer |
| Containerization | Docker + docker-compose | Local and prod |
| IaC (optional) | Terraform | Only if deploying to AWS |
| CI/CD | GitHub Actions | Free tier sufficient |
| Testing | pytest | Unit + integration |

---

## Project Structure

```
financial-intelligence-platform/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example                  # Template — never commit .env
├── .gitignore
├── Makefile                      # Common commands: make test, make run, make seed-mock
├── Dockerfile
├── docker-compose.yml
├── terraform/                    # Optional — Phase 5+ only
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── ecs/
│       ├── s3/
│       ├── lambda/
│       └── rds/
├── data/
│   ├── raw/                      # Downloaded source files (gitignored)
│   ├── processed/                # Cleaned Parquet files (gitignored)
│   ├── mock/                     # Checked-in mock/synthetic data
│   │   ├── earnings_transcripts/ # 5–10 synthetic transcripts
│   │   ├── sec_filings/          # 5–10 synthetic 10-K excerpts
│   │   ├── market_data/          # OHLCV CSVs for 10 tickers, 3 years
│   │   ├── options_chains/       # Synthetic historical chains
│   │   ├── macro/                # FRED data (real, freely downloadable)
│   │   └── news/                 # 50–100 synthetic headlines
│   └── embeddings/               # Cached vector embeddings (gitignored)
├── src/
│   ├── __init__.py
│   ├── config.py                 # Pydantic Settings — all env vars
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetchers/             # One module per data source
│   │   │   ├── sec_edgar.py
│   │   │   ├── yfinance_fetcher.py
│   │   │   ├── fred_fetcher.py
│   │   │   ├── news_fetcher.py
│   │   │   └── mock_fetcher.py   # Returns mock data — same interface
│   │   ├── processors/
│   │   │   ├── cleaner.py
│   │   │   ├── parquet_writer.py
│   │   │   └── chunker.py        # Document chunking for RAG
│   │   ├── store.py              # Unified read interface (DuckDB locally, Athena prod)
│   │   └── pipeline.py           # Orchestrates fetch → process → store
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embedder.py           # Generate embeddings
│   │   ├── vector_store.py       # ChromaDB read/write
│   │   ├── retriever.py          # Query → top-k chunks with metadata filtering
│   │   ├── chain.py              # Full RAG chain: rewrite → retrieve → generate
│   │   └── eval.py               # Evaluation harness
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── tools/                # Individual tools (MCP-compatible)
│   │   │   ├── market_data_tool.py
│   │   │   ├── options_chain_tool.py
│   │   │   ├── rag_query_tool.py
│   │   │   ├── technical_indicators_tool.py
│   │   │   ├── macro_data_tool.py
│   │   │   ├── news_tool.py
│   │   │   ├── options_pricer_tool.py
│   │   │   └── backtest_tool.py
│   │   ├── mcp_server.py         # MCP server exposing all tools
│   │   ├── research_agent.py     # Agent 1: fundamental + macro research
│   │   ├── quant_agent.py        # Agent 2: quantitative + options analysis
│   │   └── orchestrator.py       # LangGraph graph: routes user query → agents → response
│   ├── models/
│   │   ├── __init__.py
│   │   ├── features/
│   │   │   ├── price_features.py
│   │   │   ├── vol_features.py
│   │   │   ├── fundamental_features.py
│   │   │   ├── macro_features.py
│   │   │   └── feature_store.py  # Computes + caches all features
│   │   ├── regime_classifier.py  # HMM or XGBoost
│   │   ├── vol_forecast.py       # GARCH
│   │   ├── options_pricer.py     # Black-Scholes + Greeks
│   │   └── training/
│   │       ├── train_regime.py
│   │       └── train_vol.py
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── strategies/
│   │   │   ├── base.py           # Abstract strategy class
│   │   │   ├── vol_selling.py    # Sell iron condors when vol overpriced
│   │   │   └── regime_switch.py  # Long/short vol based on regime
│   │   ├── engine.py             # vectorbt wrapper with options P&L logic
│   │   └── reporting.py          # Metrics, equity curve, tearsheet
│   └── api/
│       ├── __init__.py
│       ├── main.py               # FastAPI app
│       ├── routes/
│       │   ├── research.py
│       │   ├── signals.py
│       │   ├── backtest.py
│       │   ├── options.py
│       │   └── health.py
│       ├── middleware.py          # Auth, rate limiting, logging
│       └── schemas.py            # Pydantic request/response models
├── tests/
│   ├── conftest.py               # Shared fixtures, mock data loaders
│   ├── unit/
│   │   ├── test_chunker.py
│   │   ├── test_retriever.py
│   │   ├── test_options_pricer.py
│   │   ├── test_features.py
│   │   └── test_backtest_engine.py
│   └── integration/
│       ├── test_rag_chain.py
│       ├── test_agent_flow.py
│       └── test_api_endpoints.py
├── notebooks/                    # Exploration only — no production code
│   ├── 01_data_exploration.ipynb
│   ├── 02_rag_prototyping.ipynb
│   ├── 03_model_training.ipynb
│   └── 04_backtest_analysis.ipynb
└── scripts/
    ├── seed_mock_data.py         # Generate all mock/synthetic data
    ├── build_embeddings.py       # One-off: embed all docs into ChromaDB
    ├── run_pipeline.py           # Daily data pipeline
    └── run_backtest.py           # CLI backtest runner
```

---

## Dependencies (Pinned)

```toml
# pyproject.toml
[project]
name = "financial-intelligence-platform"
requires-python = ">=3.13"

dependencies = [
    # Core
    "pydantic>=2.5,<3.0",
    "pydantic-settings>=2.1,<3.0",
    "python-dotenv>=1.0,<2.0",

    # Data
    "pandas>=2.1,<3.0",
    "numpy>=1.26,<2.0",
    "duckdb>=0.10,<1.0",
    "pyarrow>=14.0,<16.0",
    "yfinance>=0.2.36,<0.3",
    "fredapi>=0.5,<0.6",
    "sec-edgar-downloader>=5.0,<6.0",

    # LLM / RAG
    "langchain>=0.3,<0.4",
    "langchain-anthropic>=0.3,<0.4",
    "langchain-openai>=0.2,<0.3",
    "langgraph>=0.2,<0.3",
    "chromadb>=0.4,<0.6",
    "sentence-transformers>=2.3,<3.0",

    # MCP
    "mcp>=1.0,<2.0",

    # ML / Quant
    "scikit-learn>=1.4,<2.0",
    "xgboost>=2.0,<3.0",
    "arch>=6.2,<7.0",
    "hmmlearn>=0.3,<0.4",
    "vectorbt>=0.26,<0.27",
    "ta>=0.11,<0.12",

    # API
    "fastapi>=0.109,<0.200",
    "uvicorn>=0.27,<0.30",
    "httpx>=0.27,<0.28",

    # Monitoring / Utils
    "structlog>=24.1,<25.0",
    "rich>=13.7,<14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-asyncio>=0.23,<0.24",
    "pytest-cov>=4.1,<5.0",
    "ruff>=0.2,<0.3",
    "pre-commit>=3.6,<4.0",
]

aws = [
    "boto3>=1.34,<2.0",
]
```

---

## Mock Data Strategy

Real data is used when freely available. When not, synthetic mock data is generated to have the **same schema and realistic distributions** so all code works identically against mock or real data.

### What's Real vs. Mock

| Data | Real or Mock | Source / Method |
|---|---|---|
| OHLCV price data | **Real** | yfinance — free, reliable, 20+ years for major tickers |
| FRED macro data | **Real** | FRED API — free, no key needed for basic access |
| SEC 10-K/10-Q filings | **Real** | SEC EDGAR — free, public |
| Earnings call transcripts | **Mock** | LLM-generated synthetic transcripts mimicking real format. 10 tickers × 4 quarters = 40 documents |
| Historical options chains | **Mock** | Synthetic: compute Black-Scholes prices from historical underlying price + realized vol estimate. Generate chains at standard strike intervals (±5%, ±10%, ±15%, ±20% from spot) for standard tenors (7, 14, 30, 60, 90 DTE) |
| News headlines | **Mock** | LLM-generated synthetic headlines with sentiment labels. 100 headlines across 10 tickers |
| Options greeks | **Mock** | Computed analytically from synthetic chains via Black-Scholes greeks formulas |

### Mock Data Generator Script: `scripts/seed_mock_data.py`

This script must be runnable standalone:
```bash
make seed-mock  # Generates all mock data into data/mock/
```

**Synthetic options chain logic:**
```
For each ticker, for each trading day in the historical period:
  1. Get the real closing price (from yfinance data)
  2. Estimate IV = 20-day realized vol × 1.1 (IV premium approximation)
  3. For each standard strike (spot × [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]):
     For each tenor [7, 14, 30, 60, 90] days:
       - Compute call price via Black-Scholes(S=spot, K=strike, T=tenor/252, r=risk_free, σ=IV)
       - Compute put price via put-call parity
       - Compute greeks: delta, gamma, theta, vega
       - Add small random noise (±2%) to simulate bid-ask and market microstructure
  4. Save as Parquet: data/mock/options_chains/{ticker}/{date}.parquet
```

**Synthetic earnings transcript logic:**
```
For each ticker, for each quarter:
  1. Get real revenue/EPS from yfinance fundamentals
  2. Prompt an LLM (Claude) to generate a ~2000 word transcript with sections:
     - CEO opening remarks
     - CFO financial review (using real numbers)
     - Guidance
     - Analyst Q&A (3–4 questions)
  3. Include realistic metadata: date, participants, ticker
  4. Save as text: data/mock/earnings_transcripts/{ticker}_Q{q}_{year}.txt
```

### Fetcher Interface Pattern

All fetchers implement the same interface. Code never knows if it's using real or mock data:

```python
# src/data/fetchers/base.py
from abc import ABC, abstractmethod
import pandas as pd

class BaseFetcher(ABC):
    @abstractmethod
    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame: ...

    @abstractmethod
    def get_options_chain(self, ticker: str, date: str) -> pd.DataFrame: ...

    @abstractmethod
    def get_earnings_transcript(self, ticker: str, quarter: str, year: int) -> str: ...

    @abstractmethod
    def get_macro(self, indicator: str, start: str, end: str) -> pd.DataFrame: ...

# src/data/fetchers/live_fetcher.py — calls yfinance, FRED, EDGAR
# src/data/fetchers/mock_fetcher.py — reads from data/mock/
```

Controlled by config:
```python
# src/config.py
class Settings(BaseSettings):
    DATA_SOURCE: Literal["live", "mock"] = "mock"  # Default to mock for dev
```

---

## Phase 1: Project Skeleton + Data Layer (Weeks 1–3)

### Week 1: Scaffold + Mock Data

**Task 1.1** — Initialize project
```
Create the full directory structure shown above.
Create pyproject.toml with all pinned dependencies.
Create .env.example with: ANTHROPIC_API_KEY, OPENAI_API_KEY, DATA_SOURCE=mock
Create .gitignore (include data/raw/, data/processed/, data/embeddings/, .env, __pycache__, *.pyc)
Create Makefile with targets: install, test, lint, run, seed-mock
```

**Task 1.2** — Implement config module
```
Create src/config.py using pydantic-settings.
Fields: DATA_SOURCE (mock|live), ANTHROPIC_API_KEY, OPENAI_API_KEY,
        CHROMA_PERSIST_DIR (default: ./data/embeddings),
        DB_PATH (default: ./data/local.db)
Load from .env file.
Write test: tests/unit/test_config.py — verify defaults load correctly.
```

**Task 1.3** — Implement Black-Scholes pricer
```
Create src/models/options_pricer.py
Implement: bs_call_price, bs_put_price, delta, gamma, theta, vega, rho
Use scipy.stats.norm for CDF/PDF.
Inputs: S (spot), K (strike), T (time in years), r (risk-free rate), sigma (volatility)
Write test: tests/unit/test_options_pricer.py
  - Verify put-call parity: C - P = S - K*exp(-rT)
  - Verify ATM delta ≈ 0.50 for calls
  - Verify known textbook values (e.g., Hull examples)
This pricer is used in Phase 1 (mock data generation) and Phase 4 (backtesting).
```

**Task 1.4** — Build mock data generator
```
Create scripts/seed_mock_data.py
Tickers: ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "SPY", "QQQ", "TSLA", "META", "JPM"]
Date range: 2022-01-01 to 2024-12-31

Step 1: Download real OHLCV via yfinance → save to data/mock/market_data/{ticker}.parquet
Step 2: Download real FRED data (VIX, DGS10, DGS2, FEDFUNDS, CPIAUCSL) → data/mock/macro/
Step 3: Generate synthetic options chains using options_pricer.py → data/mock/options_chains/
Step 4: Generate synthetic earnings transcripts (use Claude API) → data/mock/earnings_transcripts/
Step 5: Generate synthetic news headlines (use Claude API) → data/mock/news/headlines.parquet

Make idempotent: skip steps whose output files already exist.
Add CLI flag: --force to regenerate all.
```

**Task 1.5** — Write tests for mock data integrity
```
tests/unit/test_mock_data.py
- Verify all 10 tickers have OHLCV data with no gaps > 5 business days
- Verify options chains have correct strike structure
- Verify put-call parity holds within 2% for synthetic options
- Verify earnings transcripts exist for all ticker-quarter combos
```

### Week 2: Fetcher Interface + Data Store

**Task 1.6** — Implement fetcher interface and mock fetcher
```
Create src/data/fetchers/base.py — abstract base class (as shown above)
Create src/data/fetchers/mock_fetcher.py — reads Parquet/text files from data/mock/
Write test: tests/unit/test_mock_fetcher.py — verify all methods return correct dtypes/schemas
```

**Task 1.7** — Implement live fetcher
```
Create src/data/fetchers/yfinance_fetcher.py — wraps yfinance for OHLCV + fundamentals
Create src/data/fetchers/fred_fetcher.py — wraps fredapi
Create src/data/fetchers/sec_edgar.py — wraps sec-edgar-downloader for 10-K/10-Q
Create src/data/fetchers/live_fetcher.py — composes the above, implements BaseFetcher
```

**Task 1.8** — Implement local data store
```
Create src/data/store.py
Class DataStore:
  - __init__ takes a directory path (default: data/processed/)
  - query(sql: str) → pd.DataFrame — runs SQL against Parquet files via DuckDB
  - save(df: pd.DataFrame, table_name: str, partition_cols: list) — writes Parquet
  - list_tables() → list of available tables

Example usage:
  store = DataStore()
  df = store.query("SELECT * FROM market_data WHERE ticker = 'AAPL' AND date > '2024-01-01'")

Write test: tests/unit/test_store.py
```

### Week 3: Pipeline Orchestration + Validation

**Task 1.9** — Data pipeline orchestrator
```
Create src/data/pipeline.py
Class DataPipeline:
  - __init__ takes a BaseFetcher and DataStore
  - run_daily(tickers: list, date: str) — fetches new data, processes, saves
  - run_backfill(tickers: list, start: str, end: str) — bulk historical load
  - Each step logs: ticker, source, rows fetched, rows saved, duration

Create scripts/run_pipeline.py — CLI entry point
  Usage: python scripts/run_pipeline.py --mode backfill --start 2022-01-01 --end 2024-12-31
         python scripts/run_pipeline.py --mode daily
```

**Task 1.10** — Integration test
```
tests/integration/test_pipeline.py
- Run pipeline in mock mode for 2 tickers, 1 month of data
- Verify data lands in store and is queryable via DuckDB
- Verify no look-ahead bias: data for date D only includes information available on date D
```

### Phase 1 Deliverable
Run `make seed-mock && make test` — all green. You have a working data layer, queryable locally, with realistic mock data.

---

## Phase 2: RAG Pipeline (Weeks 4–7)

### Week 4: Document Processing + Embeddings

**Task 2.1** — Document chunker
```
Create src/data/processors/chunker.py
Function: chunk_document(text: str, metadata: dict) → list[Chunk]

Chunk dataclass:
  - text: str
  - metadata: dict (ticker, doc_type, date, section, chunk_index)
  - token_count: int

Chunking rules:
  - Split on section headers (detect "## ", "Management Discussion", "Risk Factors", etc.)
  - Within sections, split at ~400 tokens with 50-token overlap
  - Never split mid-sentence
  - Preserve section name in metadata

Write test: tests/unit/test_chunker.py
  - Verify chunks don't exceed 500 tokens
  - Verify overlap exists between consecutive chunks
  - Verify metadata propagates correctly
```

**Task 2.2** — Embedder
```
Create src/rag/embedder.py
Class Embedder:
  - __init__ takes model_name (default: "text-embedding-3-small")
  - embed_texts(texts: list[str]) → list[list[float]]
  - embed_query(query: str) → list[float]
  - Batch in groups of 100 to respect rate limits
  - Cache results to avoid re-embedding unchanged documents

For testing / CI, add a MockEmbedder that returns random 256-dim vectors.
Controlled by config: EMBEDDER_MODE = "live" | "mock"
```

**Task 2.3** — Vector store wrapper
```
Create src/rag/vector_store.py
Class VectorStore:
  - __init__ creates/loads ChromaDB collection at CHROMA_PERSIST_DIR
  - add_chunks(chunks: list[Chunk], embeddings: list) — upsert with metadata
  - search(query_embedding: list, top_k: int, filters: dict) → list[Chunk]
    filters example: {"ticker": "AAPL", "doc_type": "10-K"}
  - count() → int
  - clear() — for testing

Write test: tests/unit/test_vector_store.py
  - Add 10 chunks, search, verify top result is correct
  - Verify metadata filtering works
```

**Task 2.4** — Build embeddings script
```
Create scripts/build_embeddings.py
  1. Load all documents from data/mock/earnings_transcripts/ and data/mock/sec_filings/
  2. Chunk each document
  3. Embed all chunks
  4. Store in ChromaDB
  5. Log: total docs, total chunks, total tokens, duration, cost estimate

Usage: python scripts/build_embeddings.py --source mock
Add Makefile target: make build-embeddings
```

### Weeks 5–6: RAG Chain

**Task 2.5** — Retriever
```
Create src/rag/retriever.py
Class Retriever:
  - __init__ takes VectorStore and Embedder
  - retrieve(query: str, top_k: int = 5, filters: dict = None) → list[RetrievedChunk]
  - RetrievedChunk includes: text, metadata, relevance_score

  Query rewriting step (optional but recommended):
    - Send query to Claude with system prompt:
      "Rewrite this financial question for optimal semantic search retrieval.
       Return only the rewritten query."
    - Use rewritten query for embedding + search

Write test: tests/unit/test_retriever.py
```

**Task 2.6** — RAG chain
```
Create src/rag/chain.py
Class RAGChain:
  - __init__ takes Retriever
  - ask(query: str, filters: dict = None) → RAGResponse

  RAGResponse:
    - answer: str
    - sources: list[Source] (text snippet, doc name, section)
    - confidence: float (self-assessed by LLM)

  Pipeline:
    1. Retrieve top-k chunks
    2. Build prompt: system message + retrieved context + user query
    3. System prompt instructs LLM to:
       - Answer only from provided context
       - Cite sources by [doc_name, section]
       - Say "insufficient information" if context doesn't support an answer
    4. Call Claude API
    5. Parse response into RAGResponse

Write test: tests/integration/test_rag_chain.py
  - Seed mock transcripts, build embeddings
  - Ask known question, verify answer references correct source
  - Ask out-of-scope question, verify "insufficient information" response
```

### Week 7: Evaluation + Refinement

**Task 2.7** — Evaluation harness
```
Create src/rag/eval.py
Eval dataset: data/mock/eval/rag_eval.json — 25 question-answer pairs you write manually.

Format:
[
  {
    "question": "What was AAPL's revenue guidance for Q1 2024?",
    "expected_answer_contains": ["$XX billion", "guidance"],
    "expected_source_ticker": "AAPL",
    "expected_source_type": "earnings_transcript"
  }
]

Evaluation metrics:
  - Retrieval precision: % of top-5 chunks that are from the correct document
  - Answer correctness: does the answer contain expected keywords?
  - Grounding: does the answer only use info from retrieved context?
  - Latency: end-to-end time

Run: python -m src.rag.eval → prints metrics table
```

**Task 2.8** — Iterate on chunking/retrieval based on eval results
```
This is a tuning task, not a code task. Run eval, identify failure modes:
- If retrieval misses: adjust chunk size, overlap, or add hybrid search (BM25 + vector)
- If answers hallucinate: tighten system prompt, reduce temperature
- If latency too high: reduce top_k, use smaller embedding model
Document findings in notebooks/02_rag_prototyping.ipynb
```

### Phase 2 Deliverable
`python -m src.rag.chain` — ask a question about an earnings call, get a grounded answer with citations. Eval harness shows >70% retrieval precision.

---

## Phase 3: Multi-Agent System + MCP (Weeks 8–11)

### Week 8: Tools

**Task 3.1** — Implement each tool as a standalone function with Pydantic I/O schemas.

Each tool lives in `src/agents/tools/` and follows this pattern:

```python
# src/agents/tools/market_data_tool.py
from pydantic import BaseModel

class MarketDataInput(BaseModel):
    ticker: str
    start_date: str
    end_date: str

class MarketDataOutput(BaseModel):
    ticker: str
    data: list[dict]  # [{date, open, high, low, close, volume}]

def get_market_data(input: MarketDataInput) -> MarketDataOutput:
    fetcher = get_fetcher()  # Returns mock or live based on config
    df = fetcher.get_ohlcv(input.ticker, input.start_date, input.end_date)
    return MarketDataOutput(ticker=input.ticker, data=df.to_dict(orient="records"))
```

Implement all 8 tools listed in the project structure. Each must:
- Have typed input/output schemas
- Work with both mock and live data
- Have a unit test

**Task 3.2** — Technical indicators tool (special case — more logic)
```
src/agents/tools/technical_indicators_tool.py
Uses `ta` library to compute:
  - RSI (14-period)
  - MACD (12, 26, 9)
  - Bollinger Bands (20-period, 2 std)
  - ATR (14-period)
  - 50-day and 200-day SMA

Input: ticker, date_range
Output: DataFrame-like dict with date + all indicators

Test: verify RSI is between 0 and 100, Bollinger upper > middle > lower
```

**Task 3.3** — Options pricer tool
```
src/agents/tools/options_pricer_tool.py
Wraps src/models/options_pricer.py with Pydantic schemas.
Input: S, K, T, r, sigma, option_type (call|put)
Output: price, delta, gamma, theta, vega, rho

Also add: iv_from_price(market_price, S, K, T, r) → implied_vol
  Use Newton-Raphson iteration to solve for sigma.

Test: round-trip — price an option, then recover IV from that price, verify sigma matches.
```

### Weeks 9–10: Agents

**Task 3.4** — Research Agent
```
Create src/agents/research_agent.py

Tools available: rag_query, news_search, macro_data
System prompt:
  "You are a financial research analyst. Given a ticker or sector query,
   produce a structured research brief covering:
   1. Recent fundamental developments (from filings/transcripts)
   2. Macro environment context
   3. Recent news sentiment
   4. Overall assessment: bullish / neutral / bearish with conviction (1-5)

   Always ground your analysis in the tool outputs. Never fabricate data."

Build as a LangGraph ReAct agent:
  - Agent decides which tools to call and in what order
  - Iterates until it has enough information
  - Produces a structured ResearchBrief (Pydantic model)

Test: run with "Analyze NVDA" against mock data, verify output schema is valid.
```

**Task 3.5** — Quant Agent
```
Create src/agents/quant_agent.py

Tools available: market_data, options_chain, options_pricer, technical_indicators
System prompt:
  "You are a quantitative analyst. Given a ticker, analyze:
   1. Technical setup (trend, momentum, support/resistance)
   2. Options market positioning (IV rank, put/call skew, term structure)
   3. Key levels and trade setup zones
   4. Volatility assessment: is IV cheap or expensive vs realized vol?

   Output a structured QuantReport."

QuantReport schema:
  - ticker: str
  - trend: str (bullish/bearish/neutral)
  - iv_rank: float (0-100)
  - iv_vs_rv: str (overpriced/fair/underpriced)
  - key_levels: dict (support: float, resistance: float)
  - technical_signals: dict (rsi: float, macd_signal: str, bb_position: str)

Test: verify output populates all fields with plausible values.
```

**Task 3.6** — Orchestrator
```
Create src/agents/orchestrator.py

LangGraph StateGraph with nodes:
  1. "router" — takes user query, determines scope
  2. "research" — runs Research Agent
  3. "quant" — runs Quant Agent
  4. "synthesizer" — combines outputs into final AnalysisReport

AnalysisReport:
  - ticker: str
  - research_brief: ResearchBrief
  - quant_report: QuantReport
  - recommendation: str (narrative synthesis)
  - suggested_strategies: list[str] (e.g., "Bull call spread", "Sell put")

Flow: router → [research, quant] (parallel) → synthesizer → output

Test: end-to-end test with mock data.
```

### Week 11: MCP Server

**Task 3.7** — MCP server
```
Create src/agents/mcp_server.py

Using the `mcp` Python SDK:
  - Register all 8 tools with their Pydantic schemas
  - Expose via stdio transport (for Claude Desktop) and SSE (for web clients)
  - Each tool call logs: tool_name, input, output, duration

Test manually: connect from Claude Desktop, call tools, verify responses.
Document setup in README: how to configure Claude Desktop to connect to this MCP server.
```

### Phase 3 Deliverable
Run `python -m src.agents.orchestrator "Analyze NVDA and suggest an options strategy"` → get a multi-source analysis report. MCP server works with Claude Desktop.

---

## Phase 4: ML Models + Backtesting (Weeks 12–17)

### Weeks 12–13: Feature Engineering

**Task 4.1** — Price features
```
Create src/models/features/price_features.py
Function: compute_price_features(ohlcv: pd.DataFrame) → pd.DataFrame

Features (all point-in-time safe):
  - returns_1d, returns_5d, returns_21d, returns_63d
  - realized_vol_20d (annualized std of daily returns × sqrt(252))
  - rsi_14, macd_signal, bb_width_20
  - sma_50, sma_200, sma_50_200_cross (1 if golden cross, -1 if death cross, 0 otherwise)
  - atr_14
  - drawdown_from_high_52w

Test: verify no NaN after warmup period, verify returns calculation against manual spot check.
```

**Task 4.2** — Volatility features
```
Create src/models/features/vol_features.py

Features:
  - iv_rank_52w: where current IV sits in 52-week range (0-100)
  - iv_minus_rv_20d: implied vol minus 20-day realized vol (vol risk premium)
  - iv_term_structure_slope: (60DTE IV - 30DTE IV) / 30DTE IV
  - put_call_iv_skew: 25-delta put IV minus 25-delta call IV
  - vix_level, vix_percentile_52w

For mock data: compute IV from synthetic options chains.
Test: iv_rank is between 0 and 100, skew is typically positive for equities.
```

**Task 4.3** — Macro + fundamental features
```
Create src/models/features/macro_features.py
  - yield_curve_slope (10Y - 2Y)
  - fed_funds_rate
  - vix_level
  - cpi_yoy_change

Create src/models/features/fundamental_features.py
  - earnings_sentiment_score (from RAG pipeline — query each transcript, score 1-5)
  - eps_surprise (actual/expected - 1, use yfinance or mock)

These features update quarterly or less frequently.
```

**Task 4.4** — Feature store
```
Create src/models/features/feature_store.py
Class FeatureStore:
  - build(tickers: list, start: str, end: str) → saves feature Parquet files
  - get_features(ticker: str, date: str) → dict of all features as of that date
  - get_feature_matrix(tickers: list, start: str, end: str) → pd.DataFrame
    Columns: date, ticker, feature_1, feature_2, ..., forward_return_21d (label)

  CRITICAL: All features must be point-in-time. The forward return label must be
  computed separately and NEVER included in the feature set during prediction.

Test: verify no future data leakage. For date D, all features should only use data ≤ D.
```

### Weeks 14–15: Models

**Task 4.5** — Regime classifier
```
Create src/models/regime_classifier.py

Approach: 2-state Hidden Markov Model (risk-on / risk-off)
Input features: realized_vol_20d, yield_curve_slope, vix_level, returns_21d
Training: fit on 2022-2023 data
Validation: 2024 data

Class RegimeClassifier:
  - fit(feature_matrix: pd.DataFrame) — train HMM
  - predict(features: dict) → {"regime": "risk_on"|"risk_off", "probability": float}
  - save(path) / load(path) — persist model

Create src/models/training/train_regime.py — training script
  - Load features from FeatureStore
  - Train/validate split
  - Print classification report
  - Save model to data/models/regime_classifier.pkl

Test: verify model outputs valid probabilities, regime labels are from expected set.
```

**Task 4.6** — Volatility forecast
```
Create src/models/vol_forecast.py

Approach: GARCH(1,1) model per ticker using `arch` library
Input: daily returns series
Output: predicted next-5-day annualized volatility

Class VolForecast:
  - fit(returns: pd.Series) — fit GARCH model
  - predict(returns: pd.Series) → {"forecast_vol_5d": float, "current_iv": float, "vol_signal": "overpriced"|"fair"|"underpriced"}
    vol_signal: if IV > forecast + 1std → overpriced (sell vol), if IV < forecast - 1std → underpriced (buy vol)
  - save/load

Create src/models/training/train_vol.py

Test: verify forecast is positive, verify signal logic with hand-crafted inputs.
```

### Weeks 16–17: Backtesting Engine

**Task 4.7** — Strategy base class
```
Create src/backtest/strategies/base.py

class BaseStrategy(ABC):
    @abstractmethod
    def generate_signals(self, date: str, features: dict, market_data: dict) -> list[Trade]:
        """Return list of trades to execute on this date."""
        ...

Trade dataclass:
  - ticker: str
  - direction: "long" | "short"
  - instrument: "stock" | "call" | "put"
  - strike: float | None
  - expiry: str | None
  - quantity: int
  - entry_price: float
  - stop_loss: float | None
  - take_profit: float | None
```

**Task 4.8** — Vol selling strategy
```
Create src/backtest/strategies/vol_selling.py

Logic:
  - Signal: VolForecast says IV is overpriced + RegimeClassifier says risk_on
  - Trade: Sell iron condor (sell OTM put + sell OTM call, buy further OTM wings)
    - Short strikes: ±1 standard deviation from current price
    - Wing width: 5% of underlying price
    - Tenor: 30 DTE
    - Close at 50% of max profit, or 21 DTE, or if loss > 2x premium collected
  - Position size: risk no more than 2% of portfolio per trade

Test: generate signals on known feature set, verify trade structure is valid iron condor.
```

**Task 4.9** — Regime switching strategy
```
Create src/backtest/strategies/regime_switch.py

Logic:
  - Risk-off regime → buy straddles (long vol) on SPY
  - Risk-on + vol underpriced → sell strangles on individual names
  - Risk-on + vol fair/overpriced → no trade (sit out)

Position sizing and exit rules similar to 4.8.
```

**Task 4.10** — Backtest engine
```
Create src/backtest/engine.py

Class BacktestEngine:
  - __init__(strategy: BaseStrategy, feature_store: FeatureStore, initial_capital: float = 100000)
  - run(tickers: list, start: str, end: str) → BacktestResult
  - Walk-forward day by day:
    1. Get features for today
    2. Generate signals
    3. Price new trades using synthetic options chain (or close prices for stock trades)
    4. Check exit conditions on existing positions
    5. Mark-to-market all positions using today's options prices (re-price via BS with updated S, T, σ)
    6. Log trade, update equity curve
  - Risk checks per day:
    - Max 5 concurrent positions
    - Max portfolio delta exposure: ±50 deltas
    - Max single-trade loss: 2% of equity

BacktestResult:
  - equity_curve: pd.Series (date → equity value)
  - trades: pd.DataFrame (all trades with entry/exit/pnl)
  - metrics: dict (sharpe, sortino, max_drawdown, win_rate, profit_factor, total_return, cagr)
```

**Task 4.11** — Backtest reporting
```
Create src/backtest/reporting.py

Function: generate_report(result: BacktestResult) → dict
  - Compute all metrics
  - Generate equity curve data (for plotting — don't generate images, just data)
  - Generate monthly returns table
  - Generate drawdown series
  - Save to data/processed/backtest_results/{strategy}_{timestamp}.json

Create scripts/run_backtest.py — CLI entry point
  Usage: python scripts/run_backtest.py --strategy vol_selling --start 2022-01-01 --end 2024-12-31
  Output: prints metrics table, saves full results to JSON
```

### Phase 4 Deliverable
Run backtests for both strategies, review results. The numbers don't need to be profitable — this is a learning project. But the mechanics must be correct: no look-ahead bias, proper options P&L accounting, risk limits enforced.

---

## Phase 5: API + Deployment (Weeks 18–21)

### Week 18: FastAPI Application

**Task 5.1** — API scaffolding
```
Create src/api/main.py
  - FastAPI app with CORS middleware
  - Lifespan handler: on startup, load models, initialize vector store, warm up fetchers
  - Include all routers

Create src/api/middleware.py
  - API key auth (check X-API-Key header against config)
  - Request logging (structlog: method, path, status, duration)
  - Rate limiter: 60 requests/minute per key (in-memory, simple dict + timestamps)

Create src/api/schemas.py
  - All Pydantic request/response models for every endpoint
```

**Task 5.2** — Implement routes
```
Create src/api/routes/health.py
  GET /health → {"status": "ok", "version": "0.1.0", "data_source": "mock"|"live"}

Create src/api/routes/research.py
  POST /api/v1/research → runs orchestrator, returns AnalysisReport

Create src/api/routes/signals.py
  GET /api/v1/signals?date=YYYY-MM-DD → returns all model signals for all tickers

Create src/api/routes/backtest.py
  POST /api/v1/backtest → runs backtest, returns BacktestResult

Create src/api/routes/options.py
  GET /api/v1/options/chain/{ticker} → returns options chain (mock or live)
  POST /api/v1/options/price → Black-Scholes pricing

Each route: handle errors with proper HTTP status codes, validate inputs via Pydantic.
```

**Task 5.3** — Integration tests
```
tests/integration/test_api_endpoints.py
Use FastAPI's TestClient.
- Test each endpoint with valid input → 200
- Test with missing auth → 401
- Test with invalid input → 422
- Test research endpoint returns valid AnalysisReport schema
```

### Week 19: Docker

**Task 5.4** — Containerize
```
Create Dockerfile (multi-stage build):
  Stage 1 (builder): install uv, install dependencies
  Stage 2 (runtime): copy installed packages + source code, run uvicorn

Create docker-compose.yml:
  services:
    api:
      build: .
      ports: ["8000:8000"]
      env_file: .env
      volumes:
        - ./data:/app/data  # Mount data directory
      command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000

Add Makefile targets:
  make docker-build
  make docker-run
  make docker-test  # Run tests inside container
```

**Task 5.5** — Verify full flow in Docker
```
docker-compose up → hit all endpoints with curl or httpie → all return correct responses.
This validates that the entire system works as a single container with mock data.
```

### Weeks 20–21: AWS Deployment (Optional — Terraform Path)

**Task 5.6** — Terraform infrastructure (only if deploying)
```
Create terraform/main.tf

Resources:
  - VPC with public/private subnets
  - ECR repository (for Docker image)
  - ECS Fargate cluster + service + task definition
  - Application Load Balancer
  - S3 bucket (for data — replaces local data/)
  - RDS PostgreSQL with pgvector (replaces local SQLite + Chroma)
  - Lambda function + EventBridge schedule (daily pipeline)
  - CloudWatch log groups + alarms
  - IAM roles and policies
  - Security groups

Create terraform/variables.tf
  - aws_region, environment (dev/prod), ecr_repo_name, etc.

Create terraform/outputs.tf
  - alb_dns_name, ecr_repo_url, s3_bucket_name

Usage:
  cd terraform
  terraform init
  terraform plan
  terraform apply
```

**Task 5.7** — Adapt code for AWS
```
src/data/store.py — add Athena backend (selected via config)
src/rag/vector_store.py — add pgvector backend (selected via config)
src/config.py — add AWS-specific settings: S3_BUCKET, RDS_HOST, etc.

Config-driven: the same codebase runs locally (SQLite + DuckDB + Chroma)
or on AWS (RDS + Athena + pgvector) based on environment variables.
```

**Task 5.8** — CI/CD (optional)
```
Create .github/workflows/ci.yml
  On push to main:
    1. Run linting (ruff)
    2. Run tests (pytest)
    3. Build Docker image
    4. Push to ECR (if on main branch)
    5. Deploy to ECS (if on main branch)
```

### Phase 5 Deliverable
`docker-compose up` → fully working API on localhost:8000 with all endpoints functional. Optionally, `terraform apply` deploys the same thing to AWS.

---

## Phase 6: Dashboard (Week 22 — Optional)

**Task 6.1** — Streamlit dashboard
```
Create dashboard/app.py

Pages:
  1. Research — text input for ticker, button to run analysis, display AnalysisReport
  2. Signals — table of current signals for all tickers, color-coded
  3. Backtest — dropdown for strategy, date pickers, run button, display equity curve (plotly) + metrics
  4. Options Lab — ticker input, display chain, BS calculator, P&L diagram for selected strategy

All pages call the FastAPI backend via httpx.
Add to docker-compose.yml as a second service on port 8501.
```

---

## Revised Timeline (Realistic)

| Phase | Weeks | Hours/Week | Notes |
|---|---|---|---|
| Phase 1: Skeleton + Data | 1–3 | 15–20 | Foundation — don't rush |
| Phase 2: RAG Pipeline | 4–7 | 15–20 | Extra week for eval + tuning |
| Phase 3: Agents + MCP | 8–11 | 15–20 | Extra week for MCP server |
| Phase 4: Models + Backtest | 12–17 | 15–20 | Biggest phase — 6 weeks |
| Phase 5: API + Deployment | 18–21 | 10–15 | Mostly integration, less new logic |
| Phase 6: Dashboard | 22 | 10 | Optional polish |

**Total: ~22 weeks part-time (5–6 months), or ~12 weeks full-time.**

---

## Cost Estimate

| Item | Estimated Cost |
|---|---|
| OpenAI embeddings (text-embedding-3-small) | ~$5–10 total |
| Anthropic Claude API (agents, transcript generation) | ~$20–40 total |
| AWS (if deploying — Phases 5+) | ~$50–80/month |
| AWS (if not deploying — local only) | $0 |
| All data sources | $0 (mock + free APIs) |
| **Total (local-only path)** | **~$30–50** |
| **Total (with AWS deployment)** | **~$100–200** |

---

## Claude Code Usage Notes

When feeding phases to Claude Code:

1. **Feed one task at a time** — e.g., "Implement Task 1.3: Black-Scholes pricer" with the full spec above.
2. **Always include the project structure** — paste the folder tree so Claude Code knows where files go.
3. **Always include the relevant Pydantic schemas** — Claude Code produces better code when input/output contracts are explicit.
4. **Run tests after each task** — `make test` should stay green throughout.
5. **Use the config pattern** — remind Claude Code that all data access goes through config (mock vs live) so tests never hit real APIs.
6. **Commit after each task** — git history lets you rollback if Claude Code produces something broken.