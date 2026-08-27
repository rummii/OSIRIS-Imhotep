"""Live test: download a saved SOW as a valid .docx."""
import io
import zipfile

import httpx

BASE = "https://osiris-frontend-890958491914.us-central1.run.app"
c = httpx.Client(base_url=BASE, timeout=60)

r = c.post("/api/auth/login", json={"username": "admin", "password": "2ghLPX6mKaX4QpQ1"})
print("LOGIN", r.status_code)
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

r2 = c.post(
    "/api/sow",
    json={
        "title": "Docx Export Test",
        "content_md": "# Roof Inspection\n\n**Client:** Acme\n\n## Scope\n\n- Inspect roof\n- Estimate cost\n\n| Item | Amount |\n|---|---:|\n| Labor | 1000.00 |\n| Total | 1000.00 |",
        "content_plain": '{"project_title": "Roof Inspection"}',
    },
    headers=h,
)
did = r2.json().get("id")
print("CREATE", r2.status_code, "id=", did)

r3 = c.get(f"/api/sow/{did}/download-docx", headers=h)
print("DOCX", r3.status_code, "content-type:", r3.headers.get("content-type"), "size:", len(r3.content))
if r3.status_code == 200:
    z = zipfile.ZipFile(io.BytesIO(r3.content))
    print("VALID DOCX PARTS:", z.namelist())
    xml = z.read("word/document.xml").decode("utf-8")
    print("HAS TITLE:", "Roof Inspection" in xml)
    print("HAS TABLE:", "<w:tbl>" in xml)
else:
    print("BODY:", r3.text[:300])

c.delete(f"/api/sow/{did}", headers=h)
print("CLEANUP done")
