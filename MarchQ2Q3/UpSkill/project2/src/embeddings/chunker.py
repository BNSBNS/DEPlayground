"""Recursive character text splitter for document chunking."""

from __future__ import annotations

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks using recursive character splitting.

    Tries separators in order: paragraph -> line -> sentence -> word -> char.
    Each chunk is at most ``chunk_size`` characters, with ``overlap`` characters
    shared between consecutive chunks.
    """
    if not text or not text.strip():
        return []

    raw = _split_recursive(text, chunk_size, _SEPARATORS)
    chunks = _apply_overlap(raw, overlap)
    return [c for c in chunks if c.strip()]


def _split_recursive(
    text: str,
    chunk_size: int,
    separators: list[str],
) -> list[str]:
    """Recursively split text using the first separator that produces sub-chunks."""
    if len(text) <= chunk_size:
        return [text]

    sep = separators[0]
    remaining_seps = separators[1:]

    if sep == "":
        # Character-level: hard-cut at chunk_size
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(sep)
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If a single part exceeds chunk_size, split it with finer separators
            if len(part) > chunk_size and remaining_seps:
                chunks.extend(_split_recursive(part, chunk_size, remaining_seps))
            elif len(part) > chunk_size:
                chunks.extend(
                    [part[i : i + chunk_size] for i in range(0, len(part), chunk_size)]
                )
            else:
                current = part
                continue
            current = ""

    if current:
        chunks.append(current)

    return chunks


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Add overlap from the end of the previous chunk to the start of the next."""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap:]
        result.append(prev_tail + chunks[i])
    return result
