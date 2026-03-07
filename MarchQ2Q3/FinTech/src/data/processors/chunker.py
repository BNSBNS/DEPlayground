"""Structure-aware document chunker for financial documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    text: str
    doc_name: str
    section: str = ""
    chunk_index: int = 0
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


# Section headers for different document types (case-insensitive via re.IGNORECASE)
_10K_SECTIONS = [
    r"item\s+1a[\.\:]?\s*risk\s+factors",
    r"item\s+7[\.\:]?\s*management.s\s+discussion",
    r"item\s+7a[\.\:]?\s*quantitative",
    r"item\s+8[\.\:]?\s*financial\s+statements",
]

_TRANSCRIPT_SECTIONS = [
    r"(?:ceo|chief\s+executive)\s+(?:remarks|commentary|prepared)",
    r"(?:cfo|chief\s+financial)\s+(?:remarks|commentary|prepared)",
    r"q[\&\s]*a\s+(?:session|portion)",
    r"question[\s-]*and[\s-]*answer",
    r"opening\s+remarks",
    r"closing\s+remarks",
]

_ALL_SECTION_PATTERNS = _10K_SECTIONS + _TRANSCRIPT_SECTIONS


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens using tiktoken."""
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split document into (section_name, section_text) pairs."""
    combined = "|".join(f"({p})" for p in _ALL_SECTION_PATTERNS)
    splits = re.split(f"({combined})", text, flags=re.IGNORECASE)

    sections: list[tuple[str, str]] = []
    current_name = "introduction"
    current_text = ""

    for part in splits:
        if part is None:
            continue
        is_header = any(re.match(p, part.strip(), re.IGNORECASE) for p in _ALL_SECTION_PATTERNS)
        if is_header:
            if current_text.strip():
                sections.append((current_name, current_text.strip()))
            current_name = part.strip()
            current_text = ""
        else:
            current_text += part

    if current_text.strip():
        sections.append((current_name, current_text.strip()))

    return sections if sections else [("full_document", text)]


def _split_section_into_chunks(
    text: str,
    max_tokens: int = 1024,
    overlap_tokens: int = 100,
    encoding_name: str = "cl100k_base",
) -> list[str]:
    """Split a section into token-bounded chunks, never mid-sentence."""
    enc = tiktoken.get_encoding(encoding_name)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = len(enc.encode(sentence))
        if current_tokens + sent_tokens > max_tokens and current:
            chunks.append(" ".join(current))
            # Overlap: keep last few sentences that fit within overlap budget
            overlap: list[str] = []
            overlap_count = 0
            for s in reversed(current):
                t = len(enc.encode(s))
                if overlap_count + t > overlap_tokens:
                    break
                overlap.insert(0, s)
                overlap_count += t
            current = overlap
            current_tokens = overlap_count

        current.append(sentence)
        current_tokens += sent_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_document(
    text: str,
    doc_name: str,
    max_tokens: int = 1024,
    overlap_tokens: int = 100,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Chunk a document with structure-aware splitting.

    Splits on section headers first, then into token-bounded chunks
    within each section. Never splits mid-sentence.
    """
    sections = _split_into_sections(text)
    chunks: list[Chunk] = []
    idx = 0

    for section_name, section_text in sections:
        sub_chunks = _split_section_into_chunks(
            section_text, max_tokens=max_tokens, overlap_tokens=overlap_tokens
        )
        for sub in sub_chunks:
            token_count = _count_tokens(sub)
            chunks.append(
                Chunk(
                    text=sub,
                    doc_name=doc_name,
                    section=section_name,
                    chunk_index=idx,
                    token_count=token_count,
                    metadata=metadata or {},
                )
            )
            idx += 1

    return chunks
