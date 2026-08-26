"""One-command CRUD sanity check against any DATABASE_URL.

Usage:
    # Local SQLite (default)
    python deploy/test_db_connection.py

    # Neon / Supabase / any external Postgres
    export DATABASE_URL="postgres://user:pass@host.neon.tech/db?sslmode=require"
    python deploy/test_db_connection.py

    # Cloud SQL (unix-socket)
    export DATABASE_URL="postgres+pg8000://user:pass@/db?unix_sock=/cloudsql/.../.s.PGSQL.5432"
    python deploy/test_db_connection.py

Exits 0 on success, prints a green check for each operation.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

# Allow `python deploy/test_db_connection.py` to import `backend.app.*`
BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# Override DATABASE_URL from the environment BEFORE importing the app
# (Settings is cached at import time).
os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL", ""))

from app.config import Settings  # noqa: E402
from app.services.auth_service import AuthService, UserStore  # noqa: E402

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def main() -> int:
    settings = Settings()
    dsn = settings.database_url.strip()
    backend_type = "PostgreSQL" if dsn else "SQLite (local file)"

    print(f"{YELLOW}-> Target : {backend_type}{RESET}")
    if dsn:
        # Strip the password before printing
        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        host = parsed.hostname or "<unix-socket>"
        print(f"   Host   : {host}")
        print(f"   DB     : {parsed.path.lstrip('/') or '(none)'}")
    print()

    # Use a temp DB path for SQLite; ignored for PG.
    tmp_path = str(Path(tempfile.gettempdir()) / f"osiris_dbtest_{uuid.uuid4().hex[:8]}.db")
    try:
        store = UserStore(tmp_path, dsn)
        # AuthService wraps the store and provides ensure_superadmin()
        auth = AuthService(settings)
        auth.store = store  # use the same temp file
        # Force superadmin seeding
        try:
            auth.ensure_superadmin()
            print(f"{GREEN}OK{RESET}  ensure_superadmin")
        except Exception as e:
            print(f"{RED}FAIL{RESET} ensure_superadmin: {e}")
            return 1

        # Use a unique username so the test is re-runnable
        uname = f"dbtest_{uuid.uuid4().hex[:8]}"
        try:
            store.create_user(
                username=uname,
                password="InitialPass123!",
                display_name="DB Test User",
                email=f"{uname}@example.com",
                role="user",
            )
            print(f"{GREEN}OK{RESET}  create_user")
        except Exception as e:
            print(f"{RED}FAIL{RESET} create_user: {e}")
            return 1

        # read
        try:
            u = store.get_by_username(uname)
            assert u and u["username"] == uname, f"user not found: {u}"
            assert u["is_active"], "user should be active by default"
            print(f"{GREEN}OK{RESET}  get_by_username  (id={u['id']})")
        except Exception as e:
            print(f"{RED}FAIL{RESET} read_user: {e}")
            return 1

        # update password
        try:
            store.set_password(u["id"], "UpdatedPass456!", must_change=False)
            u2 = store.get_by_username(uname)
            assert u2 is not None
            print(f"{GREEN}OK{RESET}  set_password")
        except Exception as e:
            print(f"{RED}FAIL{RESET} update_password: {e}")
            return 1

        # update profile
        try:
            updated = store.update_user(u["id"], {"display_name": "Updated Name", "is_active": True})
            assert updated and updated["display_name"] == "Updated Name"
            print(f"{GREEN}OK{RESET}  update_user")
        except Exception as e:
            print(f"{RED}FAIL{RESET} update_user: {e}")
            return 1

        # list
        try:
            all_users = store.list_users()
            assert any(x["username"] == uname for x in all_users), "user missing from list"
            print(f"{GREEN}OK{RESET}  list_users      (total={len(all_users)})")
        except Exception as e:
            print(f"{RED}FAIL{RESET} list_users: {e}")
            return 1

        # record_login
        try:
            store.record_login(u["id"])
            u3 = store.get_by_username(uname)
            assert u3 and u3.get("last_login_at"), "last_login_at should be set"
            print(f"{GREEN}OK{RESET}  record_login")
        except Exception as e:
            print(f"{RED}FAIL{RESET} record_login: {e}")
            return 1

        # delete
        try:
            ok = store.delete_user(uname)
            assert ok, "delete_user returned False"
            u4 = store.get_by_username(uname)
            assert u4 is None, "user still exists after delete"
            print(f"{GREEN}OK{RESET}  delete_user")
        except Exception as e:
            print(f"{RED}FAIL{RESET} delete_user: {e}")
            return 1

        print()
        print(f"{GREEN}All {backend_type} operations passed.{RESET}")
        return 0
    finally:
        # Clean up SQLite temp file; PG leaves no local file
        if not dsn:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
