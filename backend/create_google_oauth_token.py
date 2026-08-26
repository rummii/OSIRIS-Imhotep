"""Create an authorized-user OAuth token for the Google Docs exporter."""
from __future__ import annotations

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Authorize Google Docs export and save an OAuth token."
    )
    parser.add_argument("client_secret_file", type=Path, help="Downloaded Google OAuth client JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("credentials/google-oauth-token.json"),
        help="Destination for the authorized-user token JSON",
    )
    args = parser.parse_args()

    if not args.client_secret_file.is_file():
        parser.error(f"Client secret file not found: {args.client_secret_file}")

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret_file, SCOPES)
    credentials = flow.run_local_server(port=0, open_browser=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(credentials.to_json(), encoding="utf-8")
    print(f"OAuth token saved to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())