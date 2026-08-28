"""Application settings loaded from environment / backend/.env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Runtime configuration for the SOW backend.

    Values are read from environment variables or a ``backend/.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # --- DeepSeek ---
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # --- Gemini vision ---
    gemini_api_key: str = ""
    gemini_vision_model: str = "gemini-2.5-flash"


    # --- App ---
    app_name: str = "OSIRIS Imhotep — Engineering SOW API"
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_mb: int = 50
    max_video_frames: int = 6
    temp_dir: str = "/tmp/tmp_uploads"  # writable in Cloud Run (/tmp is tmpfs); ignored when local dev sets TEMP_DIR

    # --- Future RAG plug-in (see services/rag_provider.py) ---
    rag_provider: str = "null"  # "null" | "vector"
    rag_endpoint: str = ""
    rag_api_key: str = ""

    # --- Auth (SSO login gate) ---
    jwt_secret: str = ""                       # leave empty to auto-generate + persist
    auth_db_path: str = "/tmp/users.db"        # writable in Cloud Run; ignored when local dev sets AUTH_DB_PATH
    database_url: str = ""                     # empty -> SQLite; else postgres+pg8000://...
    token_expiry_hours: int = 12
    superadmin_username: str = "admin"
    superadmin_display_name: str = "System Administrator"
    superadmin_email: str = ""
    superadmin_password: str = ""              # empty -> random, printed once on first seed

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
