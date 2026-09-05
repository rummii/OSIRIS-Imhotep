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
    app_env: str = "production"  # "development" or "test" enables test-only routes
    app_name: str = "OSIRIS Imhotep - Engineering SOW API"
    app_version: str = "0.1.0"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_upload_mb: int = 50
    max_video_frames: int = 6
    temp_dir: str = "/tmp/tmp_uploads"

    # --- RAG plug-in ---
    rag_provider: str = "null"
    rag_endpoint: str = ""
    rag_api_key: str = ""
    rag_db_path: str = "/tmp/rag.db"
    rag_top_k: int = 5
    rag_auto_ingest: bool = True

    # --- Phase 3: reverse-geocoding ---
    geocode_enabled: bool = True
    geocode_endpoint: str = "https://nominatim.openstreetmap.org/reverse"
    geocode_user_agent: str = "OSIRIS-Imhotep/1.0"
    geocode_timeout: float = 5.0
    geocode_zoom: int = 18

    # --- Phase 4: export gate ---
    export_costing_enabled: bool = True

    # --- Cost estimation ---
    cost_currency: str = "PHP"           # ISO-4217 code; defaults to Philippine Peso
    cost_contingency_pct: float = 10.0   # applied to subtotal by CostEstimator
    cost_vat_pct: float = 0.0            # optional VAT; 0 disables
    cost_rates_override: str = ""        # JSON string override of DEFAULT_RATES_PHP

    # --- Web scraper (Phase 2 RAG) ---
    scraper_enabled: bool = False        # master switch; per-source enable happens in admin
    scraper_rate_limit_seconds: float = 1.0
    scraper_timeout_seconds: float = 30.0
    scraper_max_retries: int = 3
    scraper_user_agent: str = "OSIRIS-Imhotep/1.0 (+compliance-bot)"

    # --- Phase 5 Track 2: rate limiting ---
    rate_limit_generate_per_minute: int = 10
    rate_limit_login_per_minute: int = 10  # strict for production; E2E suite uses per-IP buckets + reset endpoint to stay under limit
    rate_limit_generate_superadmin_per_minute: int = 60

    # --- Phase 5 Track 2: quotas ---
    quota_max_upload_mb: int = 25
    quota_max_files: int = 12
    quota_max_docs_per_user: int = 500

    # --- Auth ---
    jwt_secret: str = ""
    auth_db_path: str = "/tmp/users.db"
    database_url: str = ""
    token_expiry_hours: int = 12
    superadmin_username: str = "admin"
    superadmin_display_name: str = "System Administrator"
    superadmin_email: str = ""
    superadmin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
