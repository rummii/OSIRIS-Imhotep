"""FastAPI application entry point for the OSIRIS SOW backend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_routes import router as admin_router
from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.api.sow_routes import router as sow_router
from app.config import get_settings
from app.services.auth_service import AuthService
from app.services.media_processor import ensure_temp_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("osiris")

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    ensure_temp_dir(settings.temp_dir)
    AuthService(settings).ensure_superadmin()
    logger.info(
        "OSIRIS backend ready — model=%s rag_provider=%s",
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
    app.include_router(sow_router, prefix="/api")
    return app


app = create_app()
