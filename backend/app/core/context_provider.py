"""Pluggable context providers (RAG-ready middleware).

This module defines the seam between "raw inputs" (engineer notes + media)
and "context injected into the Gemini prompt". The MVP ships a
:class:`NullContextProvider`; a private vector database for internal company
pricing / SOPs can be plugged in later by implementing the same interface
(see ``app/services/rag_provider.py``) and flipping ``RAG_PROVIDER=vector``
in the environment — no UI or route changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextDocument:
    """A single chunk of supplemental context for the prompt."""

    source: str          # e.g. "rag:company_sops", "rag:pricebook", "static"
    content: str         # rendered text (markdown is fine)
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextProvider(ABC):
    """Interface every context / RAG provider must implement."""

    name: str = "abstract"

    @abstractmethod
    def retrieve(self, notes: str, media_summary: str) -> list[ContextDocument]:
        """Return context documents relevant to the current engagement.

        ``notes`` is the engineer's free-text field notes and ``media_summary``
        is a short manifest of the uploaded media (filenames, frame counts).
        """

    def retrieve_by_sources(
        self, source_ids: list[str]
    ) -> list[ContextDocument]:
        """Return all chunks belonging to the given source IDs.

        Optional: providers that don't have a fixed corpus (e.g. external HTTP
        endpoints) can fall through to ``[]`` by not overriding this.
        """
        return []

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class NullContextProvider(ContextProvider):
    """Default no-op provider — returns no supplemental context."""

    name = "null"

    def retrieve(self, notes: str, media_summary: str) -> list[ContextDocument]:
        return []


class ChainContextProvider(ContextProvider):
    """Merges results from an ordered list of providers."""

    name = "chain"

    def __init__(self, providers: list[ContextProvider]) -> None:
        self.providers = providers

    def retrieve(self, notes: str, media_summary: str) -> list[ContextDocument]:
        docs: list[ContextDocument] = []
        for provider in self.providers:
            try:
                docs.extend(provider.retrieve(notes, media_summary))
            except Exception:  # never let a context failure kill the request
                continue
        return docs

    def retrieve_by_sources(self, source_ids: list[str]) -> list[ContextDocument]:
        docs: list[ContextDocument] = []
        for provider in self.providers:
            try:
                docs.extend(provider.retrieve_by_sources(source_ids))
            except Exception:
                continue
        return docs
