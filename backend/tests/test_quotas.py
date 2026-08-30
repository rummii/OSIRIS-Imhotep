"""Unit + integration tests for per-user quota enforcement."""
from __future__ import annotations

import io
import tempfile
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.services.quota_service import QuotaError, QuotaService


@pytest.fixture
def quota_settings() -> Settings:
    return Settings(
        quota_max_upload_mb=25,
        quota_max_files=12,
        quota_max_docs_per_user=500,
        jwt_secret="test",
    )


def test_max_upload_bytes(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    assert svc.max_upload_bytes() == 25 * 1024 * 1024


def test_max_files(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    assert svc.max_files() == 12


def test_max_docs_per_user(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    assert svc.max_docs_per_user() == 500


def test_check_upload_file_count_ok(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    files = [MagicMock(size=1024) for _ in range(5)]
    svc.check_upload(files=files)   # no raise


def test_check_upload_file_count_violation(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    files = [MagicMock(size=1024) for _ in range(20)]
    with pytest.raises(QuotaError) as exc:
        svc.check_upload(files=files)
    assert exc.value.code == "too_many_files"


def test_check_upload_accumulated_size_violation(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    # Each file: 10 MB, 3 files = 30 MB > 25 MB cap
    files = [MagicMock(size=10 * 1024 * 1024) for _ in range(3)]
    with pytest.raises(QuotaError) as exc:
        svc.check_upload(files=files)
    assert exc.value.code == "upload_too_large"


def test_check_upload_content_length_violation(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    # 26 MB > 25 MB cap
    with pytest.raises(QuotaError) as exc:
        svc.check_upload(request_content_length=26 * 1024 * 1024)
    assert exc.value.code == "upload_too_large"


def test_check_upload_content_length_ok(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    svc.check_upload(request_content_length=20 * 1024 * 1024)   # no raise


def test_check_doc_count_ok(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    svc.check_doc_count(current_doc_count=100)   # no raise


def test_check_doc_count_at_limit_ok(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    # At the limit: 500 == 500 is OK; the NEXT doc would violate.
    svc.check_doc_count(current_doc_count=499)   # no raise


def test_check_doc_count_exceeded(quota_settings: Settings) -> None:
    svc = QuotaService(quota_settings)
    with pytest.raises(QuotaError) as exc:
        svc.check_doc_count(current_doc_count=500)
    assert exc.value.code == "doc_count_exceeded"


def test_quota_error_attributes() -> None:
    exc = QuotaError("test message", "upload_too_large")
    assert exc.code == "upload_too_large"
    assert exc.message == "test message"
    assert str(exc) == "test message"


def test_doc_save_returns_409_on_quota(test_client, standard_user_token, monkeypatch) -> None:
    """Reaching the doc-count cap returns 409 Conflict."""
    import sqlite3
    from app.config import get_settings
    from app.services.quota_service import QuotaService
    settings = get_settings()
    # Override quota so only 0 docs are allowed.
    monkeypatch.setattr(settings, "quota_max_docs_per_user", 0)
    reset_for_tests()   # reset rate limiter
    resp = test_client.post(
        "/api/sow/from-generation",
        headers={"Authorization": f"Bearer {standard_user_token[0]}"},
        json={
            "sow": {
                "project_title": "X",
                "site": "Y",
                "client": "Z",
                "executive_summary": {},
                "visual_findings": [],
                "recommended_services": [],
                "scope_breakdown": [],
                "schedule": [],
                "wbs_tree": {},
                "references": [],
            },
            "is_published": False,
        },
    )
    assert resp.status_code == 409
    data = resp.json()
    assert "quota" in data["detail"].lower() or "cap" in data["detail"].lower()


# Helper needed in the test above.
def reset_for_tests():
    from app.core.rate_limit import reset_for_tests as _rt
    _rt()