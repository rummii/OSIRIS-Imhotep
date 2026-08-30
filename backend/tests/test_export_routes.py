"""Integration tests for /api/sow/{id}/export.

Covers:
  * Auth gates (401 unauthenticated, 403 non-superadmin for costing formats).
  * Multi-format single + ZIP response handling.
  * Validation of format query string.
"""
from __future__ import annotations

import io
import zipfile

import pytest


# =============================================================================
# Auth gates
# =============================================================================

class TestAuthGates:
    def test_unauthenticated_returns_401(self, test_client, seeded_sow_doc):
        res = test_client.get(f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx")
        assert res.status_code == 401

    def test_invalid_token_returns_401(self, test_client, seeded_sow_doc):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert res.status_code == 401

    def test_superadmin_can_download_docx(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.content[:2] == b"PK"

    def test_superadmin_can_download_xlsx(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=xlsx",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert "spreadsheetml" in res.headers["content-type"]

    def test_superadmin_can_download_csv(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=csv",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]

    def test_superadmin_can_download_odt(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=odt",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.content[:2] == b"PK"

    def test_superadmin_can_download_xml(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=xml",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert "xml" in res.headers["content-type"]


# =============================================================================
# Superadmin permission gates (costing formats)
# =============================================================================

class TestCostingFormatPermissionGate:
    def test_standard_user_blocked_from_xlsx(self, test_client, seeded_sow_doc, user_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=xlsx",
            headers=user_headers,
        )
        assert res.status_code == 403
        assert "superadmin" in res.text.lower()

    def test_standard_user_blocked_from_csv(self, test_client, seeded_sow_doc, user_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=csv",
            headers=user_headers,
        )
        assert res.status_code == 403
        assert "superadmin" in res.text.lower()

    def test_standard_user_can_download_docx(self, test_client, seeded_sow_doc, user_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx",
            headers=user_headers,
        )
        assert res.status_code == 200

    def test_standard_user_can_download_xml(self, test_client, seeded_sow_doc, user_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=xml",
            headers=user_headers,
        )
        assert res.status_code == 200

    def test_standard_user_blocked_from_mixed_xlsx(self, test_client, seeded_sow_doc, user_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx,xlsx",
            headers=user_headers,
        )
        assert res.status_code == 403


# =============================================================================
# Format validation + response shapes
# =============================================================================

class TestFormatValidation:
    def test_no_format_returns_400(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=",
            headers=auth_headers,
        )
        assert res.status_code == 400

    def test_invalid_format_returns_400(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=pdf,docx",
            headers=auth_headers,
        )
        assert res.status_code == 400
        assert "pdf" in res.text.lower() or "Unsupported" in res.text

    def test_nonexistent_doc_returns_404(self, test_client, auth_headers):
        res = test_client.get("/api/sow/99999/export?formats=docx", headers=auth_headers)
        assert res.status_code == 404


class TestResponseShapes:
    def test_single_format_returns_direct_file(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.content[:2] == b"PK"
        assert "word/document.xml" in zipfile.ZipFile(io.BytesIO(res.content)).namelist()
        assert "attachment" in res.headers.get("content-disposition", "").lower()

    def test_multi_format_returns_zip(self, test_client, seeded_sow_doc, auth_headers):
        res = test_client.get(
            f"/api/sow/{seeded_sow_doc['id']}/export?formats=docx,odt,xml",
            headers=auth_headers,
        )
        assert res.status_code == 200
        with zipfile.ZipFile(io.BytesIO(res.content)) as outer:
            inner_names = set(outer.namelist())
        assert any(n.endswith(".docx") for n in inner_names)
        assert any(n.endswith(".odt") for n in inner_names)
        assert any(n.endswith(".xml") for n in inner_names)

