"""Unit tests for the audit log service."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.config import Settings
from app.services.audit_service import AuditService


@pytest.fixture
def audit_settings() -> Settings:
    tmp = Path(tempfile.mkdtemp(prefix="audit-test-"))
    return Settings(auth_db_path=str(tmp / "audit.db"), database_url="", jwt_secret="test")


def test_schema_created_on_init(audit_settings: Settings) -> None:
    AuditService(audit_settings)
    conn = sqlite3.connect(audit_settings.auth_db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_log_records_all_fields(audit_settings: Settings) -> None:
    svc = AuditService(audit_settings)
    svc.log("test_action", username="alice", role="user",
             target_type="document", target_id="42",
             outcome="success", detail="hello", ip_address="127.0.0.1")
    rows = svc.list()
    assert len(rows) == 1
    r = rows[0]
    assert r["action"] == "test_action"
    assert r["username"] == "alice"
    assert r["role"] == "user"
    assert r["target_type"] == "document"
    assert r["target_id"] == "42"
    assert r["outcome"] == "success"
    assert r["detail"] == "hello"
    assert r["ip_address"] == "127.0.0.1"
    assert r["ts"]


def test_log_denormalises_user_dict(audit_settings: Settings) -> None:
    svc = AuditService(audit_settings)
    svc.log("doc_save", user={"id": 7, "username": "bob", "role": "superadmin"})
    rows = svc.list()
    assert rows[0]["user_id"] == 7
    assert rows[0]["username"] == "bob"
    assert rows[0]["role"] == "superadmin"


def test_log_never_raises(audit_settings: Settings, monkeypatch) -> None:
    svc = AuditService(audit_settings)

    def boom(*a, **k):
        raise RuntimeError("boom")

    # Inject failure in the underlying store.  AuditService.log() must
    # catch and swallow the exception so callers never see a 5xx.
    monkeypatch.setattr(svc._store, "insert", boom)
    # Should not raise.
    svc.log("anything")
    assert svc.count() == 0


def test_list_newest_first(audit_settings: Settings) -> None:
    svc = AuditService(audit_settings)
    for i in range(5):
        svc.log(f"action_{i}", username=f"u{i}", target_type="t", target_id=str(i))
    rows = svc.list()
    assert len(rows) == 5
    assert rows[0]["action"] == "action_4"
    assert rows[-1]["action"] == "action_0"


def test_list_filter_by_user_and_action(audit_settings: Settings) -> None:
    svc = AuditService(audit_settings)
    svc.log("login", user={"id": 1, "username": "a", "role": "user"})
    svc.log("login", user={"id": 2, "username": "b", "role": "user"})
    svc.log("doc_save", user={"id": 1, "username": "a", "role": "user"})
    assert len(svc.list(user_id=1)) == 2
    assert len(svc.list(action="login")) == 2
    assert len(svc.list(user_id=1, action="doc_save")) == 1


def test_list_pagination(audit_settings: Settings) -> None:
    svc = AuditService(audit_settings)
    for i in range(10):
        svc.log(f"a_{i}", username="x")
    p1 = svc.list(limit=3, offset=0)
    p2 = svc.list(limit=3, offset=3)
    assert len(p1) == 3 and len(p2) == 3
    assert p1[0]["id"] != p2[0]["id"]


def test_count(audit_settings: Settings) -> None:
    svc = AuditService(audit_settings)
    assert svc.count() == 0
    svc.log("a", user={"id": 1, "username": "a", "role": "user"})
    svc.log("a", user={"id": 2, "username": "b", "role": "user"})
    svc.log("b", user={"id": 1, "username": "a", "role": "user"})
    assert svc.count() == 3
    assert svc.count(action="a") == 2
    assert svc.count(user_id=1) == 2


def test_login_writes_audit_entry(test_client, standard_user_token, test_settings) -> None:
    """POST /api/auth/login records a success entry with username."""
    resp = test_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpassword"},
    )
    assert resp.status_code == 200
    conn = sqlite3.connect(test_settings.auth_db_path)
    cur = conn.execute(
        "SELECT username, action, outcome FROM audit_log WHERE action='login' ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "testuser"
    assert row[2] == "success"