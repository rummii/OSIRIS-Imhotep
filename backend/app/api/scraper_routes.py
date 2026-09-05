"""Scraper management HTTP routes (superadmin only).

GET    /api/admin/scraper/sources              - List registered scrape sources
GET    /api/admin/scraper/sources/{src}        - Get source config + status
POST   /api/admin/scraper/sources/{src}/enable - Enable a source
POST   /api/admin/scraper/sources/{src}/disable - Disable a source
POST   /api/admin/scraper/scrape/{src}         - Trigger a scrape of a source
POST   /api/admin/scraper/scrape-url           - Scrape a single arbitrary URL
GET    /api/admin/scraper/status               - Master status
POST   /api/admin/scraper/enable               - Enable scraper globally
POST   /api/admin/scraper/disable              - Disable scraper globally
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.config import get_settings
from app.core.dependencies import require_superadmin
from app.services.audit_service import AuditService
from app.services.scraper_service import SCRAPE_SOURCES, get_scraper

logger = logging.getLogger("osiris.scraper.routes")
router = APIRouter(prefix="/admin/scraper", tags=["admin"], dependencies=[Depends(require_superadmin)])


def _scraper():
    settings = get_settings()
    s = get_scraper()
    s._timeout = float(settings.scraper_timeout_seconds)
    s._rate_limit = float(settings.scraper_rate_limit_seconds)
    s._max_retries = int(settings.scraper_max_retries)
    s._user_agent = settings.scraper_user_agent
    return s


class SourceStatus(BaseModel):
    source: str
    name: str
    enabled: bool
    base_url: str
    list_url: str
    domain: str
    jurisdiction: str


class MasterStatus(BaseModel):
    enabled: bool
    timeout_seconds: float
    rate_limit_seconds: float
    max_retries: int
    sources_count: int


class ScrapeResponse(BaseModel):
    source: str
    domain: str
    jurisdiction: str
    pages_scraped: int = 0
    items_found: int = 0
    chunk_count: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    chunks: list[dict] = Field(default_factory=list)


@router.get("/sources", response_model=list[SourceStatus])
def list_sources() -> list[SourceStatus]:
    s = _scraper()
    out: list[SourceStatus] = []
    for k, v in SCRAPE_SOURCES.items():
        out.append(SourceStatus(source=k, name=v["name"], enabled=s.is_enabled(k),
                                base_url=v["base_url"], list_url=v["list_url"],
                                domain=v["domain"], jurisdiction=v["jurisdiction"]))
    return out


@router.get("/sources/{src}")
def get_source(src: str) -> dict:
    if src not in SCRAPE_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {src}")
    s = _scraper()
    return {"config": SCRAPE_SOURCES[src], "enabled": s.is_enabled(src)}


@router.post("/sources/{src}/enable")
def enable_source(src: str) -> dict:
    if src not in SCRAPE_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {src}")
    settings = get_settings()
    _scraper().enable_source(src)
    AuditService(settings).log("scraper_enable_source", target_type="scraper", target_id=src, outcome="success")
    return {"ok": True, "source": src, "enabled": True}


@router.post("/sources/{src}/disable")
def disable_source(src: str) -> dict:
    if src not in SCRAPE_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {src}")
    settings = get_settings()
    _scraper().disable_source(src)
    AuditService(settings).log("scraper_disable_source", target_type="scraper", target_id=src, outcome="success")
    return {"ok": True, "source": src, "enabled": False}


@router.post("/scrape/{src}", response_model=ScrapeResponse)
def scrape_source(src: str) -> ScrapeResponse:
    if src not in SCRAPE_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {src}")
    settings = get_settings()
    if not settings.scraper_enabled:
        raise HTTPException(status_code=400, detail="Scraper disabled globally. Set SCRAPER_ENABLED=true in .env.")
    result = _scraper().scrape_source(src)
    chunks = [c for c in result.chunks if isinstance(c, dict)]
    outcome = "success" if not result.errors else "partial"
    AuditService(settings).log(
        "scraper_scrape", target_type="scraper", target_id=src, outcome=outcome,
        detail=f"pages={result.pages_scraped} chunks={len(chunks)} errors={len(result.errors)}")
    return ScrapeResponse(
        source=result.source, domain=result.domain, jurisdiction=result.jurisdiction,
        pages_scraped=result.pages_scraped, items_found=result.items_found,
        chunk_count=len(chunks), errors=result.errors,
        duration_seconds=result.duration_seconds, chunks=chunks)


class ScrapeUrlRequest(BaseModel):
    url: str
    max_chunks: int = 20


@router.post("/scrape-url", response_model=ScrapeResponse)
def scrape_url(payload: ScrapeUrlRequest) -> ScrapeResponse:
    settings = get_settings()
    if not settings.scraper_enabled:
        raise HTTPException(status_code=400, detail="Scraper disabled globally. Set SCRAPER_ENABLED=true in .env.")
    result = _scraper().scrape_url(payload.url)
    chunks = [c for c in result.chunks if isinstance(c, dict)][: payload.max_chunks]
    AuditService(settings).log(
        "scraper_scrape_url", target_type="scraper", target_id=payload.url,
        outcome="success" if not result.errors else "partial",
        detail=f"chunks={len(chunks)}")
    return ScrapeResponse(
        source=result.source, domain=result.domain, jurisdiction=result.jurisdiction,
        pages_scraped=result.pages_scraped, items_found=result.items_found,
        chunk_count=len(chunks), errors=result.errors,
        duration_seconds=result.duration_seconds, chunks=chunks)


@router.get("/status", response_model=MasterStatus)
def get_status() -> MasterStatus:
    settings = get_settings()
    return MasterStatus(
        enabled=settings.scraper_enabled, timeout_seconds=settings.scraper_timeout_seconds,
        rate_limit_seconds=settings.scraper_rate_limit_seconds,
        max_retries=settings.scraper_max_retries, sources_count=len(SCRAPE_SOURCES))


@router.post("/enable")
def enable_scraper() -> dict:
    settings = get_settings()
    AuditService(settings).log("scraper_global_enable", target_type="scraper", target_id="global",
                               outcome="success", detail="Set SCRAPER_ENABLED=true in .env to persist")
    return {"ok": True, "message": "Scraper enabled. Set SCRAPER_ENABLED=true in .env to persist."}


@router.post("/disable")
def disable_scraper() -> dict:
    settings = get_settings()
    AuditService(settings).log("scraper_global_disable", target_type="scraper",
                               target_id="global", outcome="success")
    return {"ok": True, "message": "Scraper disabled. Set SCRAPER_ENABLED=false in .env to persist."}

    s._timeout = float(settings.scraper_timeout_seconds)
    s._rate_limit = float(settings.scraper_rate_limit_seconds)
    s._max_retries = int(settings.scraper_max_retries)
    s._user_agent = settings.scraper_user_agent
    return s

