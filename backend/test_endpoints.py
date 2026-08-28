"""Endpoint smoke tests using FastAPI's TestClient (no external calls).

Deterministic by design: settings are patched with empty API keys + a throwaway
SQLite auth DB, so error paths (401/502/503) are exercised WITHOUT touching the
live DeepSeek, Gemini, Google, or real user-store.
"""
import io
import os
import sys
import tempfile
import traceback

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.auth_service import AuthService
import app.api.routes as routes_module
import app.api.auth_routes as auth_routes_module
import app.api.admin_routes as admin_routes_module
import app.core.dependencies as dependencies_module

TEST_DB = os.path.join(tempfile.gettempdir(), "osiris_test_users.db")
try:
    os.remove(TEST_DB)
except FileNotFoundError:
    pass

TEST_SETTINGS = Settings(
    _env_file=None,
    deepseek_api_key="",
    gemini_api_key="",
    jwt_secret="test-secret-value",
    auth_db_path=TEST_DB,
    superadmin_username="admin",
    superadmin_password="TestAdmin123!",
)
routes_module.get_settings = lambda: TEST_SETTINGS
auth_routes_module.get_settings = lambda: TEST_SETTINGS
admin_routes_module.get_settings = lambda: TEST_SETTINGS
dependencies_module.get_settings = lambda: TEST_SETTINGS

AuthService(TEST_SETTINGS).ensure_superadmin()


def build_valid_jpeg() -> bytes:
    """A real, decodable JPEG so the media pipeline accepts the upload."""
    img = np.zeros((80, 120, 3), dtype=np.uint8)
    img[:] = (200, 160, 100)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def main() -> int:
    try:
        client = TestClient(create_app())

        # 1. Health is public ------------------------------------------------
        r = client.get("/api/health")
        assert r.status_code == 200, r.text
        print("HEALTH_OK")

        # 2. Protected endpoints reject anonymous calls ----------------------
        r = client.post("/api/sow/generate", data={"notes": "x"})
        assert r.status_code == 401, r.text
        print("UNAUTH_401_OK")

        # 3. Bad login --------------------------------------------------------
        r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401, r.text
        print("BAD_LOGIN_401_OK")

        # 4. Superadmin login ------------------------------------------------
        token = login(client, "admin", "TestAdmin123!")
        headers = {"Authorization": f"Bearer {token}"}
        print("LOGIN_OK")

        # 5. Notes-only -> DeepSeek missing key -> 502 ------------------------
        r = client.post("/api/sow/generate", data={"notes": "AHU-1 excessive vibration"}, headers=headers)
        assert r.status_code == 502 and "DEEPSEEK_API_KEY" in r.json()["detail"], r.text
        print("GENERATE_502_OK")

        # 6. Image + notes -> Gemini missing key -> 502 ------------------------
        r = client.post(
            "/api/sow/generate",
            data={"notes": "inspect"},
            files={"files": ("photo.jpg", io.BytesIO(build_valid_jpeg()), "image/jpeg")},
            headers=headers,
        )
        assert r.status_code == 502 and "GEMINI_API_KEY" in r.json()["detail"], r.text
        print("MEDIA_502_OK")

        # 8. /me + change password ---------------------------------------------
        r = client.get("/api/auth/me", headers=headers)
        assert r.status_code == 200 and r.json()["role"] == "superadmin", r.text
        print("ME_OK")

        r = client.post(
            "/api/auth/change-password",
            json={"current_password": "TestAdmin123!", "new_password": "NewPass456!"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        login(client, "admin", "NewPass456!")  # old password no longer works
        print("CHANGE_PASSWORD_OK")

        # 9. Admin onboards a user ---------------------------------------------
        r = client.post(
            "/api/admin/users",
            json={"username": "juan", "display_name": "Juan Engineer", "role": "user",
                  "password": "UserPass123!"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        r = client.get("/api/admin/users", headers=headers)
        user_id = next(u["id"] for u in r.json() if u["username"] == "juan")
        r = client.post(
            f"/api/admin/users/{user_id}/reset-password",
            json={"new_password": "ResetPass456!"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        print("ADMIN_ONBOARD_OK")

        # 10. New user: must change password, blocked from admin ----------------
        token2 = login(client, "juan", "ResetPass456!")
        headers2 = {"Authorization": f"Bearer {token2}"}
        r = client.get("/api/admin/users", headers=headers2)
        assert r.status_code == 403, r.text
        r = client.get("/api/auth/me", headers=headers2)
        assert r.json()["must_change_password"] is True
        print("ROLE_GATE_403_OK")

        print("ALL_ENDPOINT_TESTS_PASSED")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


