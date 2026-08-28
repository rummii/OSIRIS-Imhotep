"""Capture full 500 response to find the real error."""
import httpx

c = httpx.Client(base_url="https://osiris-imhotep-890958491914.europe-west1.run.app", timeout=30)
r = c.post("/api/auth/login", json={"username": "admin", "password": "2ghLPX6mKaX4QpQ1"})
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# Generate a real SOW
r2 = c.post(
    "/api/sow/generate",
    data={"notes": "Inspect building for cracks. Check roof. Verify structural integrity.", "site": "789 Pine St", "client": "Realty Inc"},
    headers=h,
)
sow = r2.json()["sow"]
print("Generated:", sow["project_title"])

# Try to save
r3 = c.post("/api/sow/from-generation", json={"sow": sow}, headers=h)
print("STATUS:", r3.status_code)
print("HEADERS:", dict(r3.headers))
print("BODY:", r3.text)
