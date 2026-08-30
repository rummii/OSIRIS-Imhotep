"""Pytest configuration and shared fixtures for the backend test suite."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.security import create_token
from app.services.auth_service import AuthService


def make_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        auth_db_path=str(tmp_path / "test_auth.db"),
        database_url="",
        jwt_secret="test-jwt-secret-phase5-track1",
        export_costing_enabled=True,
        superadmin_username="testadmin",
        superadmin_password="adminpassword123",
    )


def init_users_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "username TEXT NOT NULL UNIQUE,"
        "password_salt TEXT NOT NULL,"
        "password_hash TEXT NOT NULL,"
        "display_name TEXT, email TEXT,"
        "role TEXT NOT NULL DEFAULT 'user',"
        "is_active INTEGER NOT NULL DEFAULT 1,"
        "must_change_password INTEGER NOT NULL DEFAULT 0,"
        "created_at TEXT NOT NULL,"
        "last_login_at TEXT);"
    )


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    from app.main import app
    return app


@pytest.fixture(scope="session")
def test_client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


@pytest.fixture(scope="session")
def session_tmp_path() -> Path:
    return Path(tempfile.mkdtemp(prefix="osiris-test-"))


@pytest.fixture(scope="session")
def test_settings(session_tmp_path: Path) -> Settings:
    return make_test_settings(session_tmp_path)


@pytest.fixture(scope="session", autouse=True)
def _init_db(test_settings: Settings) -> None:
    conn = sqlite3.connect(test_settings.auth_db_path)
    try:
        init_users_table(conn)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def patch_settings(test_settings: Settings, monkeypatch) -> None:
    # Patch at every module that holds a direct import of get_settings
    monkeypatch.setattr("app.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.core.dependencies.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.sow_routes.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.auth_routes.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.admin_routes.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.routes.get_settings", lambda: test_settings)


@pytest.fixture(autouse=True)
def clean_db(test_settings: Settings) -> None:
    """Truncate non-superadmin users; re-create superadmin so auth tests work.
    Also initialise the audit_log table and reset the in-process rate limiter."""
    conn = sqlite3.connect(test_settings.auth_db_path)
    try:
        init_users_table(conn)
        conn.execute("DELETE FROM users WHERE role != 'superadmin'")
        # Phase 5 Track 2: init audit_log table (best-effort)
        try:
            conn.execute(                "CREATE TABLE IF NOT EXISTS audit_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,"
                "user_id INTEGER, username TEXT, role TEXT,"
                "action TEXT NOT NULL, target_type TEXT, target_id TEXT,"
                "outcome TEXT NOT NULL, detail TEXT, ip_address TEXT)"
            )
        except Exception:
            pass
        conn.commit()
        AuthService(test_settings).ensure_superadmin()
    finally:
        conn.close()
    # Phase 5 Track 2: reset per-process rate limiter state between tests.
    try:
        from app.core.rate_limit import reset_for_tests
        reset_for_tests()
    except Exception:
        pass


@pytest.fixture
def superadmin_token(test_settings: Settings) -> str:
    svc = AuthService(test_settings)
    svc.ensure_superadmin()
    user = svc.store.get_by_username(test_settings.superadmin_username)
    assert user is not None
    payload = {"sub": str(user["id"]), "username": user["username"], "role": user["role"]}
    token = create_token(payload, test_settings.jwt_secret, expires_seconds=3600)
    return token


@pytest.fixture
def standard_user_token(test_settings: Settings) -> tuple[str, int]:
    svc = AuthService(test_settings)
    user = svc.store.create_user(
        username="testuser", password="testpassword",
        display_name="Test User", email="testuser@example.com", role="user",
    )
    payload = {"sub": str(user["id"]), "username": user["username"], "role": user["role"]}
    token = create_token(payload, test_settings.jwt_secret, expires_seconds=3600)
    return token, user["id"]


@pytest.fixture
def auth_headers(superadmin_token: str) -> dict:
    return auth_header(superadmin_token)


@pytest.fixture
def user_headers(standard_user_token: tuple[str, int]) -> dict:
    return auth_header(standard_user_token[0])


@pytest.fixture
def seeded_sow_doc(test_settings: Settings, standard_user_token: tuple[str, int]) -> dict:
    """SOW saved by the standard (non-superadmin) user so they can access it."""
    from app.services.sow_service import SowService
    svc = SowService(test_settings)
    user_id = standard_user_token[1]
    full_sow = {
        "project_title": "Test SOW - HVAC Overhaul",
        "site": "Facility B", "client": "Meridian Corp",
        "generated_at": "2025-06-01T14:30:00Z", "currency": "PHP",
        "executive_summary": {
            "overview": "Assessment of HVAC system.",
            "overall_condition": "Poor",
            "priority_findings": "Chiller #2 compressor failure",
        },
        "visual_findings": [{
            "id": "VF-001", "asset": "AHU-01", "location": "Roof Level",
            "condition": "Fair", "severity": "Medium",
            "description": "Coil fins fouled; condensate pan sediment.",
            "recommended_action": "Full coil replacement.",
        }],
        "recommended_services": [{
            "id": "RS-001", "service": "HVAC Replacement",
            "asset": "AHU-01", "priority": "High",
            "quantity": 1, "unit": "lot",
            "unit_cost": 4500000.0, "total_cost": 4500000.0,
        }],
        "scope_breakdown": [
            {"phase": "Phase 1 — Decommissioning",
             "work_description": "Isolate and remove Chiller #2.",
             "deliverables": ["Isolation permits", "Equipment removal"],
             "duration_days": 10, "depends_on": [], "sequence": 1},
            {"phase": "Phase 2 — Mechanical Installation",
             "work_description": "Install new chiller and AHU.",
             "deliverables": ["New units in place"],
             "duration_days": 30, "depends_on": ["Phase 1"], "sequence": 2},
        ],
        "schedule": [
            {"phase": "Phase 1 — Decommissioning",        "start_day": 1,  "duration_days": 10},
            {"phase": "Phase 2 — Mechanical Installation", "start_day": 11, "duration_days": 30},
        ],
        "wbs_tree": {
            "1": {"name": "Phase 1 — Decommissioning",        "level": 1, "parent": None},
            "2": {"name": "Phase 2 — Mechanical Installation", "level": 1, "parent": None},
        },
        "references": [],
    }
    row = svc.save_from_sow(user_id=user_id, sow_dict=full_sow)
    svc.store.update(row["id"], user_id, {"content_plain": json.dumps(full_sow)})
    return row
