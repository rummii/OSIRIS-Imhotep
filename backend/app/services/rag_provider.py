"""Context provider registry + a ready-made vector DB adapter placeholder.

The MVP default is the ``null`` provider. To wire in a private RAG /
vector database (internal pricing, SOPs, past project histories):

1. Implement retrieval against your vector store in a new class here
   (the ``HttpRagContextProvider`` below is a working skeleton that POSTs a
   query to a generic HTTP endpoint and parses ``{documents: [...]}``).
2. Set ``RAG_PROVIDER=vector`` and ``RAG_ENDPOINT`` in ``backend/.env``.

Nothing else in the codebase needs to change — the prompt builder and the
``/api/sow/generate`` route only depend on the ``ContextProvider`` interface.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

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


def get_context_provider(settings: Settings) -> ContextProvider:
    """Build the configured context provider chain.

    ``ChainContextProvider`` keeps the door open for layering multiple
    sources (e.g. static SOPs + vector pricebook) without refactoring callers.
    """
    providers: list[ContextProvider] = []

    if settings.rag_provider.strip().lower() == "vector":
        providers.append(
            HttpRagContextProvider(
                endpoint=settings.rag_endpoint,
                api_key=settings.rag_api_key,
            )
        )

    if not providers:
        return NullContextProvider()
    if len(providers) == 1:
        return providers[0]
    return ChainContextProvider(providers)
