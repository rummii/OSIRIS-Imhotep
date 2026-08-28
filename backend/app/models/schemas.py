"""Pydantic models describing a generated Scope of Work payload.

``SOW_SCHEMA`` is the JSON object schema handed to the Gemini API via
``generation_config.response_schema`` so the model emits exactly this shape.
The Pydantic models are the single source of truth used to validate /
coerce whatever JSON actually comes back, so the rest of the app (frontend,
Google Docs exporter) always consumes a consistent structure.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Gemini response_schema (dict form, mirrors the Pydantic models below)
# ---------------------------------------------------------------------------
SOW_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "project_title": {"type": "STRING"},
        "site": {"type": "STRING", "nullable": True},
        "client": {"type": "STRING", "nullable": True},
        "generated_at": {"type": "STRING"},
        "currency": {"type": "STRING"},
        "executive_summary": {
            "type": "OBJECT",
            "properties": {
                "overview": {"type": "STRING"},
                "overall_condition": {"type": "STRING"},
                "priority_findings": {"type": "STRING", "nullable": True},
            },
            "required": ["overview", "overall_condition"],
        },
        "visual_findings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "asset": {"type": "STRING"},
                    "location": {"type": "STRING"},
                    "condition": {"type": "STRING"},
                    "severity": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "oem_reference": {"type": "STRING", "nullable": True},
                    "recommended_action": {"type": "STRING"},
                },
                "required": ["id", "asset", "severity", "description", "recommended_action"],
            },
        },
        "recommended_services": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "service": {"type": "STRING"},
                    "asset": {"type": "STRING"},
                    "priority": {"type": "STRING"},
                    "quantity": {"type": "INTEGER"},
                    "unit": {"type": "STRING"},
                    "unit_cost": {"type": "NUMBER"},
                    "total_cost": {"type": "NUMBER"},
                    "notes": {"type": "STRING", "nullable": True},
                },
                "required": ["id", "service", "priority", "quantity", "unit"],
            },
        },

        "scope_breakdown": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "phase": {"type": "STRING"},
                    "work_description": {"type": "STRING"},
                    "deliverables": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                    },
                    "duration_days": {"type": "INTEGER"},
                },
                "required": ["phase", "work_description"],
            },
        },
        "cost_breakdown": {
            "type": "OBJECT",
            "properties": {
                "labor": {"type": "NUMBER"},
                "materials": {"type": "NUMBER"},
                "equipment": {"type": "NUMBER"},
                "subtotal": {"type": "NUMBER"},
                "contingency_pct": {"type": "NUMBER"},
                "contingency": {"type": "NUMBER"},
                "total": {"type": "NUMBER"},
            },
            "required": ["labor", "materials", "equipment", "subtotal", "contingency_pct", "contingency", "total"],
        },
    },
    "required": [
        "project_title",
        "executive_summary",
        "visual_findings",
        "recommended_services",
        "scope_breakdown",
        "cost_breakdown",
    ],
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ExecutiveSummary(BaseModel):
    overview: str = ""
    overall_condition: str = "Not assessed"
    priority_findings: Optional[str] = None

class VisualFinding(BaseModel):
    id: str = ""
    asset: str = ""
    location: str = ""
    condition: str = ""
    severity: str = "Info"
    description: str = ""
    oem_reference: Optional[str] = None
    recommended_action: str = ""

class RecommendedService(BaseModel):
    id: str = ""
    service: str = ""
    asset: str = ""
    priority: str = "Medium"
    quantity: float = 1
    unit: str = "lump sum"
    unit_cost: float = 0.0
    total_cost: float = 0.0
    notes: Optional[str] = None

class ScopeItem(BaseModel):
    phase: str = ""
    work_description: str = ""
    deliverables: list[str] = Field(default_factory=list)
    duration_days: int | None = 0

class CostBreakdown(BaseModel):
    currency: str = "PHP"
    labor: float = 0.0
    materials: float = 0.0
    equipment: float = 0.0
    subtotal: float = 0.0
    contingency_pct: float = 10.0
    contingency: float = 0.0
    total: float = 0.0

class SowResponse(BaseModel):
    project_title: str = "Untitled Scope of Work"
    site: Optional[str] = None
    client: Optional[str] = None
    generated_at: str = ""
    currency: str = "PHP"
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    visual_findings: list[VisualFinding] = Field(default_factory=list)
    recommended_services: list[RecommendedService] = Field(default_factory=list)
    scope_breakdown: list[ScopeItem] = Field(default_factory=list)
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)

class GroundingSource(BaseModel):
    title: str = ""
    url: str = ""

class MediaLogEntry(BaseModel):
    filename: str
    kind: str
    status: str = "ok"
    detail: str = ""
    frames: int = 0

class GenerateResponse(BaseModel):
    """Response body of POST /api/sow/generate."""
    sow: SowResponse
    media_log: list[MediaLogEntry] = Field(default_factory=list)
    model: str = ""
    grounding: bool = True
    grounding_sources: list[GroundingSource] = Field(default_factory=list)
    context_provider: str = "null"
    generated_at: str = ""
    document_id: Optional[int] = None

# ---------------------------------------------------------------------------
# Lenient coercion from raw Gemini JSON -> SowResponse
# ---------------------------------------------------------------------------

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default

def coerce_sow_payload(data: dict[str, Any]) -> SowResponse:
    """Normalise a raw Gemini JSON object into a validated ``SowResponse``.

    The model occasionally omits optional fields or emits strings where
    numbers are expected — this helper fills defaults and re-computes the
    cost totals so downstream consumers never see a malformed payload.
    """
    cost = data.get("cost_breakdown") or {}
    currency = str(data.get("currency") or cost.get("currency") or "PHP")
    labor = _to_float(cost.get("labor"))
    materials = _to_float(cost.get("materials"))
    equipment = _to_float(cost.get("equipment"))
    subtotal = _to_float(cost.get("subtotal")) or (labor + materials + equipment)
    contingency_pct = _to_float(cost.get("contingency_pct"), 10.0)
    contingency = _to_float(cost.get("contingency")) or round(subtotal * contingency_pct / 100.0, 2)
    total = _to_float(cost.get("total")) or round(subtotal + contingency, 2)

    services: list[dict[str, Any]] = []
    for item in data.get("recommended_services") or []:
        if not isinstance(item, dict):
            continue
        unit_cost = _to_float(item.get("unit_cost"))
        qty = _to_float(item.get("quantity"), 1.0)
        total_cost = _to_float(item.get("total_cost")) or round(unit_cost * qty, 2)
        services.append({**item, "quantity": qty, "unit_cost": unit_cost, "total_cost": total_cost})

    sow_data = {
        "project_title": str(data.get("project_title") or "Untitled Scope of Work"),
        "site": data.get("site"),
        "client": data.get("client"),
        "generated_at": str(data.get("generated_at") or ""),
        "currency": currency,
        "executive_summary": data.get("executive_summary") or {},
        "visual_findings": [f for f in data.get("visual_findings") or [] if isinstance(f, dict)],
        "recommended_services": services,
        "scope_breakdown": [
            {**s, "duration_days": _to_int(s.get("duration_days"))}
            for s in (data.get("scope_breakdown") or []) if isinstance(s, dict)
        ],
        "cost_breakdown": {
            "currency": currency,
            "labor": labor,
            "materials": materials,
            "equipment": equipment,
            "subtotal": subtotal,
            "contingency_pct": contingency_pct,
            "contingency": contingency,
            "total": total,
        },
    }
    return SowResponse.model_validate(sow_data)

