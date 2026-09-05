"""FastAPI application entry point for the OSIRIS SOW backend."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin_routes import (
    router as admin_router,
    audit_router,
    config_router,
    compliance_router,
)
from app.api.cost_routes import router as cost_router
from app.api.rag_routes import router as rag_router
from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.api.scraper_routes import router as scraper_router
from app.api.sop_routes import router as sop_router
from app.api.sow_routes import router as sow_router
from app.config import get_settings
from app.core.rate_limit import reset_for_tests
from app.services.auth_service import AuthService
from app.services.media_processor import ensure_temp_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("osiris")

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/


def _auto_ingest(settings) -> None:
    """Seed the RAG corpus on first boot if sqlite_vec is enabled and the store is empty."""
    if settings.rag_provider.strip().lower() != "sqlite_vec":
        return
    try:
        from app.services.ingest_service import IngestService

        service = IngestService(settings)
        stats = service.stats()
        if stats.get("total_chunks", 0) == 0 and settings.rag_auto_ingest:
            logger.info("RAG corpus is empty - running auto-ingest on first boot ...")
            result = service.refresh_corpus()
            logger.info(
                "Auto-ingest complete: %d chunks embedded in %.2fs (engine=%s, errors=%d)",
                result.chunks_embedded,
                result.duration_seconds,
                result.engine,
                len(result.errors),
            )
        else:
            logger.info(
                "RAG stats: %d chunks (engine=%s)",
                stats.get("total_chunks", 0),
                stats.get("engine", "unknown"),
            )
    except Exception as exc:
        logger.warning("RAG auto-ingest skipped: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    ensure_temp_dir(settings.temp_dir)
    AuthService(settings).ensure_superadmin()
    # Run RAG auto-ingest in the background so it does not block startup
    if settings.rag_provider.strip().lower() == "sqlite_vec":
        asyncio.get_event_loop().run_in_executor(None, _auto_ingest, settings)
    logger.info(
        "OSIRIS backend ready - model=%s rag_provider=%s",
        settings.deepseek_model,
        settings.rag_provider,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(audit_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(compliance_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")
    app.include_router(sow_router, prefix="/api")
    app.include_router(sop_router, prefix="/api")
    app.include_router(cost_router, prefix="/api")
    app.include_router(scraper_router, prefix="/api")

    # Test-only endpoint: clears the in-memory rate-limit buckets so the
    # E2E suite can run multiple flood tests without poisoning the
    # browser-login bucket (127.0.0.1) for the rest of the suite.  Refused
    # in production when APP_ENV is not development/test/ci.
    @app.post("/api/_test/reset-rate-limit")
    async def _reset_rate_limit(request: Request) -> JSONResponse:
        if not settings.app_env.strip().lower().startswith(("test", "dev", "ci")):
            return JSONResponse({"error": "not allowed"}, status_code=403)
        reset_for_tests()
        return JSONResponse({"ok": True})

    return app


app = create_app()
