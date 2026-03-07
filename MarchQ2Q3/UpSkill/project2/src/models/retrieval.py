"""Models for hybrid retrieval and query responses."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    content: str
    source: Literal["vector", "graph"]
    score: float
    metadata: dict[str, Any] = {}
    reasoning_path: str = ""


class QueryIntent(StrEnum):
    lineage = "lineage"
    metadata = "metadata"
    definition = "definition"
    change = "change"
    general = "general"


class QueryResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=0.95)
    sources: list[RetrievalResult] = []
    reasoning_path: str = ""
    cypher_used: str | None = None
