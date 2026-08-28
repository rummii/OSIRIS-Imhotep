"""Debug: see why /api/sow/from-generation returns 500."""
import httpx

c = httpx.Client(base_url="https://osiris-imhotep-890958491914.europe-west1.run.app", timeout=30)
r = c.post("/api/auth/login", json={"username": "admin", "password": "2ghLPX6mKaX4QpQ1"})
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

sow = {
    "project_title": "Debug Test",
    "currency": "PHP",
    "executive_summary": {"overview": "x", "overall_condition": "good"},
    "visual_findings": [],
    "recommended_services": [],
    "scope_breakdown": [],
    "cost_breakdown": {
        "currency": "PHP",
        "labor": 0,
        "materials": 0,
        "equipment": 0,
        "subtotal": 0,
        "contingency_pct": 0,
        "contingency": 0,
        "total": 0,
    },
    "generated_at": "2026-01-01T00:00:00Z",
}

r2 = c.post("/api/sow/from-generation", json={"sow": sow}, headers=h)
print("STATUS:", r2.status_code)
print("BODY:", r2.text[:1500])
