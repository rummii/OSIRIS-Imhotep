"""Per-user quota enforcement.

Three quotas are enforced:

* ``max_upload_bytes``       - single SOW generation submission cap (default 25 MB)
* ``max_files_per_submission`` - max number of media files in one request (default 12)
* ``max_docs_per_user``      - max saved SOW documents per user (default 500)

Cap values are sourced from the ``Settings`` object so operators can
override per environment.  Violations raise :class:`QuotaError` which
the route layer maps to an appropriate 4xx HTTP status.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from app.config import Settings

logger = logging.getLogger("osiris.quota")


class QuotaError(RuntimeError):
    """Raised on quota violation.

    ``code`` is a short machine-readable tag used by the route layer to
    map the error to a status code:
      * "upload_too_large"      -> 413
      * "too_many_files"        -> 400
      * "doc_count_exceeded"    -> 409
    """

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class QuotaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # -- per-request upload limits --------------------------------------------

    def max_upload_bytes(self) -> int:
        return int(self.settings.quota_max_upload_mb) * 1024 * 1024

    def max_files(self) -> int:
        return int(self.settings.quota_max_files)

    def check_upload(
        self,
        *,
        files: Optional[Iterable] = None,
        request_content_length: Optional[int] = None,
    ) -> None:
        """Enforce upload size + file count caps for a single request.

        ``files`` - iterable of UploadFile-like objects (each has ``.size``)
        ``request_content_length`` - optional Content-Length header in bytes
        """
        # 1. file count
        if files is not None:
            count = 0
            total = 0
            for f in files:
                count += 1
                size = getattr(f, "size", None)
                if isinstance(size, int):
                    total += size
            if count > self.max_files():
                raise QuotaError(
                    f"Too many files in submission: {count} (max {self.max_files()}).",
                    code="too_many_files",
                )
            # 2. accumulated size from files (only if UploadFile exposed .size)
            if total > self.max_upload_bytes():
                raise QuotaError(
                    f"Upload too large: {total} bytes (max {self.max_upload_bytes()}).",
                    code="upload_too_large",
                )
        # 3. Content-Length header fallback
        if request_content_length is not None and request_content_length > self.max_upload_bytes():
            raise QuotaError(
                f"Upload too large: {request_content_length} bytes (max {self.max_upload_bytes()}).",
                code="upload_too_large",
            )

    # -- per-user saved-document cap ------------------------------------------

    def max_docs_per_user(self) -> int:
        return int(self.settings.quota_max_docs_per_user)

    def check_doc_count(self, *, current_doc_count: int) -> None:
        if current_doc_count >= self.max_docs_per_user():
            raise QuotaError(
                f"Document cap reached: you already have {current_doc_count} "
                f"saved documents (max {self.max_docs_per_user()}). "
                f"Delete old documents to free up space.",
                code="doc_count_exceeded",
            )
