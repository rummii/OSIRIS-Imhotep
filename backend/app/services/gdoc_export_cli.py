"""Standalone Google Docs export runner.

Spawned as a subprocess by ``POST /api/sow/export-gdoc`` so the Google API
calls execute in a *fresh* Python process. The long-lived uvicorn worker
threads can stall on Google's HTTPS endpoints on some Windows setups, while a
fresh process completes reliably (validated: refresh -> build -> create).

Usage::

    python -m app.services.gdoc_export_cli <input.json> <output.json>

``input.json``::

    {"sow": {...}, "owner_email": "..."}

``output.json``::

    {"ok": true, "doc_url": "...", "doc_id": "..."}
    # or
    {"ok": false, "error": "..."}
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from app.config import get_settings
from app.models.schemas import SowResponse
from app.services.gdoc_service import GdocNotConfiguredError, GoogleDocsService


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: gdoc_export_cli <input.json> <output.json>", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    result: dict = {"ok": False, "error": "unknown export error"}

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
        sow = SowResponse.model_validate(payload.get("sow", payload))
        owner_email = payload.get("owner_email")

        service = GoogleDocsService(get_settings())
        doc_url, doc_id = service.create_sow_document(sow, owner_email)
        result = {"ok": True, "doc_url": doc_url, "doc_id": doc_id}
    except GdocNotConfiguredError as exc:
        result = {"ok": False, "error": str(exc), "status": 503}
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        # Google blocks service accounts from creating Docs in standalone
        # (non-Workspace) projects. Surface a clear, actionable message.
        if "403" in str(exc) and ("permission" in str(exc).lower()):
            msg += (
                " — The Google service account cannot create Docs in this project "
                "(the Docs API does not support service accounts outside a Google "
                "Workspace domain). Configure a user OAuth token instead: "
                "run `python deploy/setup_oauth_token.py` locally and store the "
                "result at GOOGLE_OAUTH_TOKEN_FILE."
            )
        result = {"ok": False, "error": msg}
        traceback.print_exc(file=sys.stderr)

    try:
        output_path.write_text(json.dumps(result), encoding="utf-8")
    except OSError:
        pass
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
