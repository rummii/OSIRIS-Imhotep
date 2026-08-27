"""Set up a user OAuth token for Google Docs export (replaces the SA, which
Google does not allow to create Docs outside a Workspace domain).

Run from the repo root with the backend venv::

    cd backend
    .venv\\Scripts\\python.exe ..\\deploy\\setup_oauth_token.py

It prints a URL, asks you to paste the redirected URL back, then saves
``backend/credentials/google-oauth-token.json`` (includes a refresh token).

Deploy notes (Cloud Run):
  1. Create a secret from the token file:
       gcloud secrets create gdoc-oauth-token --data-file=backend/credentials/google-oauth-token.json
       gcloud secrets add-iam-policy-binding gdoc-oauth-token \
         --member=serviceAccount:890958491914-compute@developer.gserviceaccount.com \
         --role=roles/secretmanager.secretAccessor
  2. Attach it and point GOOGLE_OAUTH_TOKEN_FILE at a writable path:
       gcloud run services update osiris-imhotep --region=europe-west1 \\
         --update-secrets=GOOGLE_OAUTH_TOKEN_JSON=gdoc-oauth-token:latest \\
         --update-env-vars=GOOGLE_OAUTH_TOKEN_FILE=/tmp/app-data/oauth-token.json
  (main.py materializes GOOGLE_OAUTH_TOKEN_JSON -> GOOGLE_OAUTH_TOKEN_FILE.)
"""
from __future__ import annotations

import json
import socket
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
OUT = BACKEND_DIR / "credentials" / "google-oauth-token.json"
CLIENT_SECRET_FILE = BACKEND_DIR / "credentials" / "client_secret.json"


def main() -> int:
    if not CLIENT_SECRET_FILE.exists():
        print(
            "Missing OAuth client credentials.\n\n"
            "1. Open https://console.cloud.google.com/apis/credentials\n"
            "2. Create an OAuth client ID of type 'Desktop app' for project spsasean\n"
            "3. Download the JSON and save it as:\n"
            f"   {CLIENT_SECRET_FILE}\n"
            "4. Re-run this script."
        )
        return 1

    # 1. Try an existing token (refresh it if possible).
    creds = None
    if OUT.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(OUT), SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                print("Refreshed existing token.")
        except Exception as exc:  # noqa: BLE001
            print(f"Existing token unusable ({exc}); re-running the flow.")

    # 2. Run the consent flow if we still don't have valid creds.
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
        try:
            sock = socket.socket()
            sock.bind(("localhost", 0))
            port = sock.getsockname()[1]
            sock.close()
            redirect_uri = f"http://localhost:{port}/"
            flow.redirect_uri = redirect_uri
            auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
            print("Open this URL in a browser (the account that should own the docs):\n")
            print(auth_url)
            webbrowser.open(auth_url)
            code = input("\nPaste the full redirect URL (or code) here: ").strip()
            if "code=" in code:
                code = parse_qs(code.split("?", 1)[1])["code"][0]
            flow.redirect_uri = redirect_uri
            flow.fetch_token(code=code)
            creds = flow.credentials
        except Exception as exc:  # noqa: BLE001
            print(f"Automatic flow failed: {exc}")
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved token to {OUT}")
    print("Scopes:", SCOPES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
