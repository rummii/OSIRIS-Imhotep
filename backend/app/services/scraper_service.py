"""Web scraper adapter (stub for future Phase-2 live ingestion).

Per the Phase-1 scope decision, **no live scraping is performed**.  This
module exists so the architecture is future-proof: when live regulatory
fetching is enabled, callers can use ``scrape_url`` / ``scrape_source`` and
the output will feed straight into ``IngestService.refresh_corpus()``.

Today the public functions return ``NotImplementedError`` and the
:class:`ScraperService` is a no-op.  Replace each method body when
activating a real source.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.services.regulatory_corpus import Chunk

logger = logging.getLogger("osiris.scraper")


@dataclass
class ScrapeResult:
    source: str
    domain: str = ""
    jurisdiction: str = "Philippines"
    chunks: list[Chunk] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "domain": self.domain,
            "jurisdiction": self.jurisdiction,
            "chunk_count": len(self.chunks),
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class ScraperNotConfigured(RuntimeError):
    """Raised when a scraping operation is requested but no fetcher is wired up."""


class ScraperService:
    """Stub scraper adapter.

    The Phase-1 build is intentionally no-op because we ship a static seed
    corpus (see :mod:`app.services.regulatory_corpus`).  When the superadmin
    enables a live source, register it via :meth:`register_source` and
    implement the corresponding fetcher in this class.
    """

    def __init__(self) -> None:
        self._sources: dict[str, callable] = {}

    # ------------------------------------------------------------------
    # Public API (Phase 1 stubs)
    # ------------------------------------------------------------------

    def register_source(self, name: str, fetcher: callable) -> None:
        """Register a live fetcher for a named source.

        ``fetcher`` must be a callable taking no arguments and returning a
        ``list[Chunk]``.  The first time live scraping is enabled the
        superadmin can wire in fetcher implementations per source.
        """
        self._sources[name] = fetcher

    def scrape_url(self, url: str) -> ScrapeResult:
        """Future: fetch and parse a single regulatory URL.

        Phase 1 raises :class:`ScraperNotConfigured`.  When live scraping is
        enabled, replace this body with an httpx / Playwright fetch +
        BeautifulSoup parse pipeline, returning ``Chunk`` objects that the
        ``IngestService`` can persist.
        """
        raise ScraperNotConfigured(
            f"Live scraping is not enabled in Phase 1 (url={url!r}). "
            "Use the static corpus or wire a fetcher via register_source()."
        )

    def scrape_source(self, source: str) -> ScrapeResult:
        """Future: re-scrape a named source registered via :meth:`register_source`."""
        if source not in self._sources:
            raise ScraperNotConfigured(
                f"No fetcher registered for source {source!r}. "
                "Use the static corpus or call register_source() first."
            )
        fetcher = self._sources[source]
        result = ScrapeResult(source=source)
        try:
            result.chunks = fetcher()
        except Exception as exc:  # pragma: no cover
            logger.error("Fetcher for %s failed: %s", source, exc)
            result.errors.append(str(exc))
        return result

    def list_sources(self) -> list[dict]:
        """Return a list of registered sources (Phase 1 is always empty)."""
        return [
            {"source": name, "registered": True} for name in sorted(self._sources)
        ]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_scraper_instance: Optional[ScraperService] = None


def get_scraper() -> ScraperService:
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = ScraperService()
    return _scraper_instance
