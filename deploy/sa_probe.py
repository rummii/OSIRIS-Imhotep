"""Direct test: can the gdoc-sa service account create a Google Doc?"""
import os

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request

KEY = r"C:\Users\ahmad\AppData\Local\Temp\gdoc-sa-key.json"
if not os.path.exists(KEY):
    print("NO KEY AT:", KEY)
    raise SystemExit(2)

creds = service_account.Credentials.from_service_account_file(
    KEY,
    scopes=["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
)
creds.refresh(Request())
tok = creds.token
print("TOKEN OK")

r = httpx.post(
    "https://docs.googleapis.com/v1/documents",
    headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
    json={"title": "OSIRIS SA Probe"},
    timeout=30,
)
print("DOCS CREATE:", r.status_code, r.text[:400])
if r.status_code == 200:
    doc_id = r.json()["documentId"]
    print("DOC ID:", doc_id)
    r2 = httpx.delete(
        f"https://www.googleapis.com/drive/v3/files/{doc_id}",
        headers={"Authorization": f"Bearer {tok}"},
        timeout=30,
    )
    print("CLEANUP DELETE:", r2.status_code)
