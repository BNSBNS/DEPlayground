"""Research tools for agents — RAG, news, macro data."""

from __future__ import annotations

from pydantic import BaseModel

from src.agents.tools.market_tools import ToolResult
from src.data.fetchers import get_fetcher
from src.rag.embedder import MockEmbedder
from src.rag.retriever import Retriever
from src.rag.vector_store import VectorStore


class RAGQueryInput(BaseModel):
    question: str
    n_results: int = 5


class MacroDataInput(BaseModel):
    series_id: str
    start: str
    end: str


def rag_query(inp: RAGQueryInput) -> ToolResult[dict]:
    """Query the RAG pipeline for financial document Q&A."""
    try:
        embedder = MockEmbedder()
        store = VectorStore()
        retriever = Retriever(store, embedder)
        chunks = retriever.retrieve(inp.question, n_results=inp.n_results)
        return ToolResult(
            success=True,
            data={
                "question": inp.question,
                "num_results": len(chunks),
                "results": [
                    {
                        "text": c.text[:300],
                        "doc_name": c.doc_name,
                        "section": c.section,
                        "score": c.score,
                    }
                    for c in chunks
                ],
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


def get_macro_data(inp: MacroDataInput) -> ToolResult[dict]:
    """Fetch macro data series."""
    try:
        fetcher = get_fetcher()
        df = fetcher.get_macro(inp.series_id, inp.start, inp.end)
        return ToolResult(
            success=True,
            data={
                "series_id": inp.series_id,
                "rows": len(df),
                "latest_value": float(df["value"].iloc[-1]),
                "min": float(df["value"].min()),
                "max": float(df["value"].max()),
                "mean": float(df["value"].mean()),
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
