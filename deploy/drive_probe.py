"""Probe: can the gdoc-sa service account create files via the Drive API?
If Drive works, we can bypass the blocked docs.create by uploading a .docx
and converting it (mimeType application/vnd.google-apps.document).
"""
import base64
import io
import json
import zipfile

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

KEY = r"C:\Users\ahmad\AppData\Local\Temp\gdoc-sa-key.json"
creds = service_account.Credentials.from_service_account_file(
    KEY,
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"],
)
creds.refresh(Request())
tok = creds.token
H = {"Authorization": f"Bearer {tok}"}


def probe(label: str, method: str, url: str, **kw) -> httpx.Response | None:
    try:
        r = httpx.request(method, url, timeout=40, **kw)
        body = r.text[:200].replace("\n", " ")
        print(f"{label}: {r.status_code} {body}")
        return r
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: EXC {exc}")
        return None


def _make_docx(title: str, body: str) -> bytes:
    """Build a minimal valid .docx in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"))
        z.writestr("word/_rels/document.xml.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'))
        z.writestr("word/document.xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
            f"<w:p><w:r><w:t>{title}</w:t></w:r></w:p>"
            f"<w:p><w:r><w:t>{body}</w:t></w:r></w:p>"
            "</w:body></w:document>"))
    return buf.getvalue()


def _multipart(filename: str, file_mime: str, file_bytes: bytes, metadata: dict) -> bytes:
    parts = []
    parts.append(f"--osiris_boundary\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n".encode())
    parts.append(f"--osiris_boundary\r\nContent-Type: {file_mime}\r\nContent-Transfer-Encoding: base64\r\n\r\n".encode())
    parts.append(base64.b64encode(file_bytes))
    parts.append(b"\r\n--osiris_boundary--\r\n")
    return b"".join(parts)


# 1) Plain text file via Drive API (metadata + media, multipart)
r1 = probe("DRIVE text create", "POST",
           "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
           data=_multipart("hello.txt", "text/plain", b"hello world",
                           {"name": "OSIRIS probe.txt"}),
           headers={**H, "Content-Type": "multipart/related; boundary=osiris_boundary"},
           )
if r1 and r1.status_code == 200:
    fid = r1.json().get("id")
    probe("DRIVE text delete", "DELETE", f"https://www.googleapis.com/drive/v3/files/{fid}", headers=H)

# 2) Minimal .docx -> Google Doc conversion via Drive API
docx_bytes = _make_docx("OSIRIS probe doc", "Hello from OSIRIS.")
r2 = probe("DRIVE docx->gdoc create", "POST",
           "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
           data=_multipart("probe.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx_bytes,
                           {"name": "OSIRIS Probe", "mimeType": "application/vnd.google-apps.document"}),
           headers={**H, "Content-Type": "multipart/related; boundary=osiris_boundary"},
           )
if r2 and r2.status_code == 200:
    gid = r2.json().get("id")
    probe("CONVERTED gdoc id", "GET", f"https://www.googleapis.com/drive/v3/files/{gid}?fields=id,name,mimeType", headers=H)
    probe("GDOC delete", "DELETE", f"https://www.googleapis.com/drive/v3/files/{gid}", headers=H)

