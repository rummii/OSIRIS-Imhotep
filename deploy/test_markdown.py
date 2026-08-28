"""Test that _sow_to_markdown handles the schema correctly."""
import sys
sys.path.insert(0, r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend")

from app.services.sow_service import _sow_to_markdown
from app.models.schemas import SowResponse

# Realistic test SOW
sow = SowResponse(
    project_title="Test Project",
    site="123 Main St",
    client="Acme Corp",
    currency="PHP",
    generated_at="2026-01-01T00:00:00Z",
    executive_summary={
        "overview": "Test overview",
        "overall_condition": "Good",
        "priority_findings": None,
    },
    visual_findings=[{
        "id": "1",
        "asset": "Roof",
        "location": "Building A",
        "condition": "Fair",
        "severity": "Medium",
        "description": "Minor cracks observed",
        "recommended_action": "Repair within 6 months",
    }],
    recommended_services=[{
        "id": "1",
        "service": "Concrete Repair",
        "asset": "Roof",
        "priority": "High",
        "quantity": 1,
        "unit": "lump sum",
        "unit_cost": 50000,
        "total_cost": 50000,
        "notes": "Use epoxy injection",
    }],
    scope_breakdown=[{
        "phase": "Phase 1: Inspection",
        "work_description": "Perform detailed visual inspection",
        "deliverables": ["Inspection report"],
        "duration_days": 3,
    }],
    cost_breakdown={
        "currency": "PHP",
        "labor": 10000,
        "materials": 20000,
        "equipment": 5000,
        "subtotal": 35000,
        "contingency_pct": 10,
        "contingency": 3500,
        "total": 38500,
    },
)

md = _sow_to_markdown(sow)
print("Markdown generated successfully!")
print(md[:300])
