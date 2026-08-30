"""Ingestion service: chunks regulatory text and embeds it into the vector store.

The current implementation reads the static seed from
:mod:`app.services.regulatory_corpus`.  The interface (``refresh_corpus``)
is intentionally decoupled from the source so that future scrapers
(see :mod:`app.services.scraper_service`) can plug in by adding new
chunks to the input list.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from app.config import Settings
from app.core.vector_store import EMBEDDING_DIM, VectorStore
from app.services.embedder import GeminiEmbedder, get_embedder
from app.services.regulatory_corpus import get_corpus

logger = logging.getLogger("osiris.ingest")

# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[\.\?!])\s+(?=[A-Z0-9])")
_WORD_SPLIT = re.compile(r"\s+")
_MAX_WORDS_PER_CHUNK = 220
_OVERLAP_WORDS = 40


def chunk_text(text: str, max_words: int = _MAX_WORDS_PER_CHUNK, overlap: int = _OVERLAP_WORDS) -> list[str]:
    """Split ``text`` into overlapping chunks of at most ``max_words`` words.

    Long regulatory passages are first split on sentence boundaries; if a
    single sentence exceeds ``max_words`` it is hard-split on word boundaries.
    Consecutive sentences are packed into the current chunk until the word
    cap is reached; a final chunk of fewer than ``overlap`` words is merged
    into the previous one to avoid degenerate tail fragments.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]
    if not sentences:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    current_words: list[str] = []
    current_count = 0

    for sentence in sentences:
        sent_words = _WORD_SPLIT.split(sentence)
        if len(sent_words) > max_words:
            # Flush current, then hard-split the oversized sentence.
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = current_words[-overlap:] if overlap else []
                current_count = len(current_words)
            for i in range(0, len(sent_words), max_words - overlap):
                piece = sent_words[i : i + max_words]
                if len(piece) == max_words and i + max_words < len(sent_words):
                    chunks.append(" ".join(piece))
                else:
                    current_words = piece
                    current_count = len(piece)
            continue
        if current_count + len(sent_words) > max_words:
            chunks.append(" ".join(current_words))
            tail = current_words[-overlap:] if overlap else []
            current_words = tail + sent_words
            current_count = len(current_words)
        else:
            current_words.extend(sent_words)
            current_count += len(sent_words)

    if current_words:
        # Merge tiny trailing chunk into previous
        if chunks and current_count < overlap:
            chunks[-1] = chunks[-1] + " " + " ".join(current_words)
        else:
            chunks.append(" ".join(current_words))

    return chunks


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@dataclass
class IngestStats:
    docs_seen: int = 0
    chunks_embedded: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    engine: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "docs_seen": self.docs_seen,
            "chunks_embedded": self.chunks_embedded,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
            "engine": self.engine,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class IngestService:
    """Orchestrates the embedding + persistence of regulatory chunks."""

    def __init__(
        self,
        settings: Settings,
        store: Optional[VectorStore] = None,
        embedder: Optional[GeminiEmbedder] = None,
    ) -> None:
        self._settings = settings
        self._store = store or VectorStore(settings.rag_db_path)
        self._embedder = embedder
        self._initialized = False

    def _ensure_ready(self) -> None:
        if self._initialized:
            return
        if self._embedder is None:
            if not self._settings.gemini_api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not set; cannot embed the RAG corpus."
                )
            self._embedder = get_embedder(self._settings.gemini_api_key)
        self._store.init_schema()
        self._initialized = True

    def refresh_corpus(self) -> IngestStats:
        """Re-embed and upsert every chunk in the static corpus.

        Idempotent: re-running the same corpus simply replaces existing rows
        keyed on ``(source, chunk_index)``.  Returns aggregate stats.
        """
        self._ensure_ready()
        stats = IngestStats()
        started = time.monotonic()

        corpus = get_corpus()
        stats.docs_seen = len(corpus)
        stats.engine = self._store.stats().get("engine", "unknown")

        # Build a flat list of (chunk_text, source, domain, jurisdiction, citation, chunk_index)
        flat: list[dict] = []
        for doc in corpus:
            for idx, piece in enumerate(chunk_text(doc["text"])):
                flat.append(
                    {
                        "text": piece,
                        "source": doc["source"],
                        "domain": doc["domain"],
                        "jurisdiction": doc["jurisdiction"],
                        "citation": doc["citation"],
                        "chunk_index": idx,
                    }
                )

        logger.info("Refreshing RAG corpus: %d docs, %d chunks", len(corpus), len(flat))

        # Embed in batches for efficiency, but upsert one row at a time so
        # the store handles its own (source, chunk_index) uniqueness.
        batch_size = 16
        try:
            for batch_start in range(0, len(flat), batch_size):
                batch = flat[batch_start : batch_start + batch_size]
                texts = [row["text"] for row in batch]
                try:
                    embeddings = self._embedder.embed_batch_sync(texts)  # type: ignore[union-attr]
                except Exception as exc:
                    logger.error("Batch embed failed: %s", exc)
                    stats.errors.append(f"batch {batch_start}: {exc}")
                    continue
                for row, emb in zip(batch, embeddings):
                    if not emb or len(emb) != EMBEDDING_DIM:
                        stats.errors.append(
                            f"bad embedding for {row['source']}[{row['chunk_index']}]"
                        )
                        continue
                    row["embedding"] = emb
                try:
                    written = self._store.upsert_chunks(batch)
                    stats.chunks_embedded += written
                except Exception as exc:
                    logger.error("Upsert failed: %s", exc)
                    stats.errors.append(f"upsert batch {batch_start}: {exc}")
        except Exception as exc:
            logger.error("Refresh corpus failed: %s", exc)
            stats.errors.append(str(exc))

        stats.duration_seconds = time.monotonic() - started
        logger.info(
            "RAG corpus refresh complete: %d chunks in %.2fs",
            stats.chunks_embedded,
            stats.duration_seconds,
        )
        return stats

    def stats(self) -> dict:
        self._ensure_ready()
        return self._store.stats()
