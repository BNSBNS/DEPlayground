from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog

from src.ingestion.store import store

log = structlog.get_logger(__name__)


def ingest_documents(
    docs_dir: Path,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> dict[str, Any]:
    """Read all .md files in a directory, chunk them, and build graph nodes.

    Creates:
      - DocumentNode per file
      - DocumentChunkNode per chunk with PART_OF edge to its document
      - DESCRIBES edges from chunks to entities (tables/columns) mentioned in content
    """
    md_files = sorted(docs_dir.glob("*.md"))
    counts = {"documents": 0, "chunks": 0, "describes_edges": 0}

    # Collect known table/column names for entity linking.
    known_entities = _collect_known_entities()

    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        doc_name = md_path.stem
        doc_id = f"document:{doc_name}"

        store.add_node(
            doc_id,
            "Document",
            doc_name,
            path=str(md_path),
            size_bytes=len(text.encode("utf-8")),
        )
        counts["documents"] += 1

        chunks = _recursive_char_split(text, chunk_size, chunk_overlap)
        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"chunk:{doc_name}:{idx}"
            store.add_node(
                chunk_id,
                "DocumentChunk",
                f"{doc_name} chunk {idx}",
                content=chunk_text,
                index=idx,
                char_length=len(chunk_text),
            )
            store.add_edge(chunk_id, doc_id, "PART_OF")
            counts["chunks"] += 1

            # Simple entity linking: find table/column names in chunk text.
            mentioned = _find_mentioned_entities(chunk_text, known_entities)
            for entity_id in mentioned:
                store.add_edge(chunk_id, entity_id, "DESCRIBES")
                counts["describes_edges"] += 1

    log.info("docs_ingestion_complete", directory=str(docs_dir), **counts)
    return counts


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _recursive_char_split(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Split text recursively using a hierarchy of separators."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    for sep in _SEPARATORS:
        parts = text.split(sep) if sep else list(text)
        if len(parts) <= 1:
            continue

        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = f"{current}{sep}{part}" if current else part
            if len(candidate) > chunk_size and current:
                chunks.append(current)
                # Keep overlap from the tail of the previous chunk.
                current = current[-overlap:] + sep + part if overlap else part
            else:
                current = candidate
        if current.strip():
            chunks.append(current)
        if chunks:
            return chunks

    # Absolute fallback: hard-split by chunk_size.
    return [
        text[i : i + chunk_size]
        for i in range(0, len(text), chunk_size - overlap)
        if text[i : i + chunk_size].strip()
    ]


def _collect_known_entities() -> dict[str, str]:
    """Build a lowercased-name -> node_id map from existing Table and Column nodes."""
    mapping: dict[str, str] = {}
    for node in store.get_nodes_by_type("Table"):
        mapping[node["name"].lower()] = node["id"]
    for node in store.get_nodes_by_type("Column"):
        mapping[node["name"].lower()] = node["id"]
    return mapping


def _find_mentioned_entities(
    text: str,
    known: dict[str, str],
) -> list[str]:
    """Return node ids for entities whose names appear in the text."""
    text_lower = text.lower()
    found: list[str] = []
    for name, node_id in known.items():
        # Match as whole word to reduce false positives.
        if re.search(rf"\b{re.escape(name)}\b", text_lower):
            found.append(node_id)
    return found
