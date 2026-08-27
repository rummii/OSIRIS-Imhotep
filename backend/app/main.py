"""FastAPI application entry point for the OSIRIS SOW backend."""
from __future__ import annotations

import logging
import os
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


def materialize_google_credentials(settings) -> None:
    """Write ``GOOGLE_SERVICE_ACCOUNT_JSON`` / ``GOOGLE_OAUTH_TOKEN_JSON``
    (Cloud Run secret env vars) to the file paths configured in
    ``GOOGLE_SERVICE_ACCOUNT_FILE`` / ``GOOGLE_OAUTH_TOKEN_FILE`` so the
    Google Docs exporter can read them without any code changes."""
    for env_name, target_name in (
        ("GOOGLE_SERVICE_ACCOUNT_JSON", "google_service_account_file"),
        ("GOOGLE_OAUTH_TOKEN_JSON", "google_oauth_token_file"),
    ):
        json_value = os.environ.get(env_name, "").strip()
        target = getattr(settings, target_name, "").strip()
        if not json_value or not target:
            continue
        path = Path(target)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(json_value, encoding="utf-8")
            try:
                path.chmod(0o600)
            except OSError:
                pass
            logger.info("Materialised %s to %s", env_name, path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    materialize_google_credentials(settings)
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
