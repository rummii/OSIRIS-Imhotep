"""Live E2E test: SOW document persistence via the deployed frontend proxy."""
import httpx

BASE = "https://osiris-frontend-890958491914.us-central1.run.app"
c = httpx.Client(base_url=BASE, timeout=60)

r = c.post("/api/auth/login", json={"username": "admin", "password": "2ghLPX6mKaX4QpQ1"})
print("LOGIN", r.status_code)
tok = r.json().get("access_token")
h = {"Authorization": f"Bearer {tok}"}

r2 = c.post(
    "/api/sow",
    json={
        "title": "E2E Test SOW",
        "content_md": "# Test SOW\nBody",
        "content_plain": '{"project_title": "Test"}',
        "is_published": False,
    },
    headers=h,
)
print("CREATE", r2.status_code)
did = r2.json().get("id")
print("DOC_ID", did)

r3 = c.get("/api/sow?scope=mine", headers=h)
docs = r3.json().get("documents", [])
print("LIST", r3.status_code, "count=", len(docs))

r4 = c.get(f"/api/sow/{did}", headers=h)
print("GET", r4.status_code, r4.json().get("title") if r4.status_code == 200 else r4.text)

r5 = c.delete(f"/api/sow/{did}", headers=h)
print("DELETE", r5.status_code)

# Also verify an unauthenticated call is rejected
r6 = c.get("/api/sow?scope=mine")
print("UNAUTH_LIST", r6.status_code)
