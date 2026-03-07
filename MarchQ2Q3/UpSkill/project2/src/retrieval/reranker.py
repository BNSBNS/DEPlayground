"""LLM-based reranking of retrieval results."""

from __future__ import annotations

import re

from src.llm.factory import get_llm_provider
from src.logging import get_logger
from src.models.retrieval import RetrievalResult

logger = get_logger("retrieval.reranker")

_RERANK_PROMPT = (
    "Given query: {query}\n\n"
    "Rank these results by relevance. Return ONLY a comma-separated list of "
    "0-based indices in order from most to least relevant.\n\n"
    "{results}"
)


async def rerank(
    results: list[RetrievalResult],
    query: str,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Use the LLM to rerank retrieval results by relevance."""
    if len(results) <= 1:
        return results[:top_k]

    numbered = "\n".join(
        f"[{i}] {r.content[:200]}" for i, r in enumerate(results)
    )
    prompt = _RERANK_PROMPT.format(query=query, results=numbered)

    try:
        llm = get_llm_provider()
        resp = await llm.complete([{"role": "user", "content": prompt}])
        indices = _parse_indices(resp.content, len(results))

        if not indices:
            logger.warning("rerank_parse_empty", response=response[:100])
            return results[:top_k]

        reordered = [results[i] for i in indices if i < len(results)]
        # Append any results that weren't in the LLM's ranking
        seen = set(indices)
        for i, r in enumerate(results):
            if i not in seen:
                reordered.append(r)

        logger.debug("rerank_complete", query=query[:80], reordered=len(reordered))
        return reordered[:top_k]

    except Exception:
        logger.exception("rerank_failed", query=query[:80])
        return results[:top_k]


def _parse_indices(response: str, max_len: int) -> list[int]:
    """Extract integer indices from the LLM response."""
    numbers = re.findall(r"\d+", response)
    indices: list[int] = []
    seen: set[int] = set()

    for n in numbers:
        idx = int(n)
        if 0 <= idx < max_len and idx not in seen:
            indices.append(idx)
            seen.add(idx)

    return indices
