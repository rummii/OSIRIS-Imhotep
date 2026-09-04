"""Context provider registry + vector DB adapters.

Two RAG adapters ship:

* ``HttpRagContextProvider``      — POSTs the query to a configurable HTTP
  endpoint (e.g. a hosted vector-DB retrieval service).
* ``SqliteVecRagContextProvider`` — embeds the query with Gemini
  ``text-embedding-004`` and searches a local SQLite vector store
  (sqlite-vec, with a numpy-fallback path). Recommended default for
  self-contained deployments.

Set ``RAG_PROVIDER=sqlite_vec`` (or ``vector``) in ``backend/.env`` to
activate. Nothing else in the codebase needs to change — the prompt
builder and the ``/api/sow/generate`` route only depend on the
:class:`ContextProvider` interface.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Optional

from app.config import Settings
from app.core.context_provider import (
    ChainContextProvider,
    ContextDocument,
    ContextProvider,
    NullContextProvider,
)

logger = logging.getLogger("osiris.rag")


class HttpRagContextProvider(ContextProvider):
    """POSTs the query to a configurable HTTP endpoint (e.g. a vector-DB
    retrieval service) and maps the response to :class:`ContextDocument`.

    Expected response shape (JSON)::

        {"documents": [{"source": "pricebook_2026", "content": "..."}]}
    """

    name = "vector"

    def __init__(self, endpoint: str, api_key: str = "", top_k: int = 5) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.top_k = top_k

    def retrieve(self, notes: str, media_summary: str) -> list[ContextDocument]:
        if not self.endpoint:
            logger.warning("RAG_PROVIDER=vector but RAG_ENDPOINT is empty; returning no context.")
            return []

        payload = json.dumps(
            {
                "query": notes.strip() or media_summary.strip(),
                "notes": notes,
                "media_summary": media_summary,
                "top_k": self.top_k,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            f"{self.endpoint}/retrieve",
            data=payload,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.error("RAG retrieval failed: %s", exc)
            return []

        docs: list[ContextDocument] = []
        for item in body.get("documents", []):
            source = str(item.get("source") or "rag")
            content = str(item.get("content") or "").strip()
            if content:
                docs.append(ContextDocument(source=source, content=content))
        return docs


class SqliteVecRagContextProvider(ContextProvider):
    """Local RAG over the SQLite vector store (see ``app.core.vector_store``).

    Each query is embedded with Gemini ``text-embedding-004`` and the top-k
    most similar chunks are returned. Falls back to no-context behaviour if
    the embedder is unavailable (missing API key, network failure) so a
    misconfigured RAG layer never breaks SOW generation.
    """

    name = "sqlite_vec"

    def __init__(
        self,
        db_path: str,
        api_key: str = "",
        top_k: int = 5,
        domain_filter: Optional[str] = None,
    ) -> None:
        # Local imports to avoid pulling google-genai at module load
        # (the file is imported by main.py and admin routes alike).
        from app.core.vector_store import VectorStore
        from app.services.embedder import get_embedder

        self._store = VectorStore(db_path)
        self._embedder = None
        self._api_key = api_key
        self._top_k = top_k
        self._domain_filter = domain_filter
        if api_key:
            try:
                self._embedder = get_embedder(api_key)
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to initialise GeminiEmbedder: %s", exc)
        else:
            logger.warning(
                "SqliteVecRagContextProvider created without GEMINI_API_KEY; "
                "retrieval will return no context."
            )

    def retrieve(self, notes: str, media_summary: str) -> list[ContextDocument]:
        if self._embedder is None:
            return []
        query = (notes or "").strip() or (media_summary or "").strip()
        if not query:
            return []
        try:
            embedding = self._embedder.embed_sync(query)
        except Exception as exc:
            logger.error("Query embedding failed: %s", exc)
            return []
        try:
            rows = self._store.search(
                embedding,
                k=self._top_k,
                domain_filter=self._domain_filter,
            )
        except Exception as exc:
            logger.error("Vector store search failed: %s", exc)
            return []

        docs: list[ContextDocument] = []
        for row in rows:
            source = f"rag:{row.get('source', 'unknown')}"
            citation = row.get("citation", "")
            content = row["chunk_text"]
            if citation:
                content = f"[{citation}] {content}"
            docs.append(
                ContextDocument(
                    source=source,
                    content=content,
                    metadata={
                        "domain": row.get("domain", ""),
                        "jurisdiction": row.get("jurisdiction", ""),
                        "citation": citation,
                        "similarity": row.get("similarity", 0.0),
                    },
                )
            )
        return docs

    def retrieve_by_sources(
        self, source_ids: list[str]
    ) -> list[ContextDocument]:
        """Retrieve all chunks belonging to the given SOP/KB source IDs.

        Used by the SOP/KB upload feature to surface a document's own chunks
        as supplemental context during SOW generation.
        """
        if not source_ids or self._store is None:
            return []
        rows = self._store.get_by_sources(source_ids)
        docs: list[ContextDocument] = []
        for row in rows:
            citation = row.get("citation", "")
            content = row.get("chunk_text", "")
            if citation:
                content = f"[{citation}] {content}"
            docs.append(
                ContextDocument(
                    source=row.get("source", "unknown"),
                    content=content,
                    metadata={
                        "domain": row.get("domain", ""),
                        "jurisdiction": row.get("jurisdiction", ""),
                        "citation": citation,
                        "similarity": 1.0,
                    },
                )
            )
        return docs


def get_context_provider(settings: Settings) -> ContextProvider:
    """Build the configured context provider chain.

    ``ChainContextProvider`` keeps the door open for layering multiple
    sources (e.g. static SOPs + vector pricebook) without refactoring callers.
    """
    providers: list[ContextProvider] = []

    rag = settings.rag_provider.strip().lower()
    if rag == "vector":
        providers.append(
            HttpRagContextProvider(
                endpoint=settings.rag_endpoint,
                api_key=settings.rag_api_key,
                top_k=settings.rag_top_k,
            )
        )
    elif rag == "sqlite_vec":
        providers.append(
            SqliteVecRagContextProvider(
                db_path=settings.rag_db_path,
                api_key=settings.gemini_api_key,
                top_k=settings.rag_top_k,
            )
        )

    if not providers:
        return NullContextProvider()
    if len(providers) == 1:
        return providers[0]
    return ChainContextProvider(providers)
