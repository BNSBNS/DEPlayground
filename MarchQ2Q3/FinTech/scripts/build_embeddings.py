"""Load documents, chunk, embed, and store in ChromaDB."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import get_settings
from src.data.processors.chunker import chunk_document
from src.logging import configure_logging, get_logger
from src.rag.embedder import Embedder, MockEmbedder
from src.rag.vector_store import VectorStore

logger = get_logger(__name__)


def load_documents(data_dir: Path) -> list[tuple[str, str]]:
    """Load all text documents from mock data directories.

    Returns list of (doc_name, text) tuples.
    """
    docs: list[tuple[str, str]] = []

    # Earnings transcripts
    transcript_dir = data_dir / "mock" / "earnings_transcripts"
    if transcript_dir.exists():
        for f in sorted(transcript_dir.glob("*.txt")):
            docs.append((f.stem, f.read_text(encoding="utf-8")))

    # News headlines (load as single doc)
    news_dir = data_dir / "mock" / "news"
    if news_dir.exists():
        for f in sorted(news_dir.glob("*.txt")):
            docs.append((f.stem, f.read_text(encoding="utf-8")))

    logger.info("loaded_documents", count=len(docs))
    return docs


def build_embeddings(use_mock: bool = False) -> None:
    """Build embeddings from all available documents."""
    settings = get_settings()
    data_dir = Path(settings.DATA_DIR)

    docs = load_documents(data_dir)
    if not docs:
        logger.warning("no_documents_found", data_dir=str(data_dir))
        return

    # Chunk all documents
    all_chunks = []
    for doc_name, text in docs:
        chunks = chunk_document(text, doc_name)
        all_chunks.extend(chunks)
        logger.info("chunked_document", doc_name=doc_name, chunks=len(chunks))

    logger.info("total_chunks", count=len(all_chunks))

    # Embed
    embedder = MockEmbedder() if use_mock else Embedder()
    texts = [c.text for c in all_chunks]
    embeddings = embedder.embed_texts(texts)
    logger.info("embedded_chunks", count=len(embeddings))

    # Store
    store = VectorStore()
    store.add_chunks(all_chunks, embeddings)
    logger.info("stored_embeddings", total=store.count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build document embeddings")
    parser.add_argument(
        "--mock-embedder",
        action="store_true",
        help="Use mock embedder (no API calls)",
    )
    args = parser.parse_args()
    configure_logging()
    build_embeddings(use_mock=args.mock_embedder)


if __name__ == "__main__":
    main()
