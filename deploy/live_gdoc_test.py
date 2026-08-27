"""Live test: Google Docs export of a saved SOW document."""
import httpx

BASE = "https://osiris-frontend-890958491914.us-central1.run.app"
c = httpx.Client(base_url=BASE, timeout=180)

r = c.post("/api/auth/login", json={"username": "admin", "password": "2ghLPX6mKaX4QpQ1"})
tok = r.json().get("access_token")
h = {"Authorization": f"Bearer {tok}"}

r2 = c.post(
    "/api/sow",
    json={
        "title": "GDoc Export Test",
        "content_md": "# Export Test\n\nRoofing scope.",
        "content_plain": '{"project_title": "Export Test", "site": "123 Main St"}',
        "is_published": False,
    },
    headers=h,
)
did = r2.json().get("id")
print("CREATE", r2.status_code, "id=", did)

r3 = c.post(f"/api/sow/{did}/export-gdoc", json={}, headers=h)
print("EXPORT", r3.status_code)
if r3.status_code == 200:
    print("DOC_URL", r3.json().get("doc_url"))
else:
    print("EXPORT_BODY", r3.text[:500])

c.delete(f"/api/sow/{did}", headers=h)
print("CLEANUP_DELETE done")
