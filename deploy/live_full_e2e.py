"""Full E2E: generate SOW -> auto-save -> list documents -> .docx download."""
import io
import zipfile

import httpx

BASE = "https://osiris-imhotep-890958491914.europe-west1.run.app"
c = httpx.Client(base_url=BASE, timeout=60)

# 1. Login
r = c.post("/api/auth/login", json={"username": "admin", "password": "2ghLPX6mKaX4QpQ1"})
print("LOGIN", r.status_code)
assert r.status_code == 200, f"login failed: {r.text}"
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# 2. Generate SOW
r2 = c.post(
    "/api/sow/generate",
    data={"notes": "Inspect building for cracks and water damage. Check roof condition.", "site": "123 Main St", "client": "Acme Corp"},
    headers=h,
)
print("GENERATE", r2.status_code)
assert r2.status_code == 200, f"generate failed: {r2.text[:200]}"
gen = r2.json()
sow = gen["sow"]
print("  title:", sow["project_title"])

# 3. Auto-save via new endpoint
r3 = c.post(
    "/api/sow/from-generation",
    json={"sow": sow, "sow_id": None, "is_published": False},
    headers=h,
)
print("FROM-GENERATION", r3.status_code)
assert r3.status_code == 201, f"from-generation failed: {r3.text[:200]}"
saved = r3.json()
doc_id = saved["id"]
print("  saved doc_id:", doc_id)

# 4. List documents (should now be non-empty)
r4 = c.get("/api/sow?scope=mine", headers=h)
print("LIST DOCS", r4.status_code)
docs = r4.json()["documents"]
print("  count:", len(docs), "— first title:", docs[0]["title"] if docs else "(empty)")

# 5. Download .docx
r5 = c.get(f"/api/sow/{doc_id}/download-docx", headers=h)
print("DOCX", r5.status_code, "size:", len(r5.content))
assert r5.status_code == 200
z = zipfile.ZipFile(io.BytesIO(r5.content))
xml = z.read("word/document.xml").decode("utf-8")
print("  HAS TITLE:", sow["project_title"] in xml)
print("  VALID DOCX:", z.namelist())

# 6. Export to Google Docs (should still fail with SA)
r6 = c.post(f"/api/sow/{doc_id}/export-gdoc", json={}, headers=h)
print("EXPORT-GDOC", r6.status_code, r6.json().get("detail", "")[:60])

# 7. Cleanup
c.delete(f"/api/sow/{doc_id}", headers=h)
print("CLEANUP done ✓")
