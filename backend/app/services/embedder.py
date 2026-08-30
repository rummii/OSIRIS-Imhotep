"""Embedding client backed by Gemini text-embedding-004.

Wraps the ``google-genai`` client (already a project dependency) and exposes
a simple ``embed`` / ``embed_batch`` interface returning 768-dim dense
vectors.  Results are cached in a thread-safe LRU so repeated queries never
hit the API twice.
"""
from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from threading import Lock
from typing import Optional

from google import genai

logger = logging.getLogger("osiris.embedder")

EMBEDDING_DIM = 768
_LRU_SIZE = 256


class GeminiEmbedder:
    def __init__(self, api_key: str, cache_size: int = _LRU_SIZE) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set.  Add it to backend/.env to use the RAG vector engine."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = "text-embedding-004"
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_size = cache_size
        self._lock = Lock()

    def embed_sync(self, text: str) -> list[float]:
        key = hashlib.sha256(text.encode()).hexdigest()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        try:
            response = self._client.models.embed_content(model=self._model, contents=text)
        except Exception as exc:
            logger.error("Gemini embed failed (text[:60]=%r): %s", text[:60], exc)
            return [0.0] * EMBEDDING_DIM
        values = self._normalize_dim(list(response.embeddings[0].values))
        with self._lock:
            if len(self._cache) >= self._cache_size:
                self._cache.popitem(last=False)
            self._cache[key] = values
        return values

    def embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.models.embed_content(model=self._model, contents=texts)
        except Exception as exc:
            logger.error("Gemini embed_batch failed: %s", exc)
            return [[0.0] * EMBEDDING_DIM for _ in texts]
        return [self._normalize_dim(list(e.values)) for e in response.embeddings]

    async def embed(self, text: str) -> list[float]:
        return self.embed_sync(text)

    def _normalize_dim(self, values: list[float]) -> list[float]:
        if len(values) == EMBEDDING_DIM:
            return values
        if len(values) < EMBEDDING_DIM:
            return values + [0.0] * (EMBEDDING_DIM - len(values))
        return values[:EMBEDDING_DIM]


_embedder_instance: Optional[GeminiEmbedder] = None


def get_embedder(api_key: str) -> GeminiEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = GeminiEmbedder(api_key)
    return _embedder_instance
