"""Dynamic cost estimation for SOW line items.

Computes labor, materials, and equipment costs from RecommendedService line
items using a rate catalog (per-currency) that can be overridden via Settings
or a custom provider. Philippine Peso (PHP) defaults are sourced from common
DPWH / DOLE-published daily-wage and rental rates as of 2024-2025; these are
fallback heuristics only and are NOT official quotations.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.config import Settings
from app.models.schemas import CostBreakdown, RecommendedService

logger = logging.getLogger("osiris.cost")


DEFAULT_RATES_PHP = {
    "labor": {
        "default": 650.0, "skilled": 850.0, "unskilled": 500.0,
        "foreman": 1100.0, "electrician": 900.0, "welder": 950.0,
        "mason": 750.0, "carpenter": 750.0, "painter": 600.0,
        "plumber": 800.0, "operator": 850.0,
    },
    "materials": {
        "default": 500.0,     # PHP per unit (bag, linear meter, etc.)
        "cement": 280.0,      # per 40-kg bag
        "concrete": 7500.0,   # per cubic meter
        "steel": 95.0,        # per kg (rebar)
        "rebar": 95.0,        # per kg
        "lumber": 15.0,       # per board foot
        "pipe": 350.0,        # per linear meter
        "paint": 450.0,       # per gallon
        "tile": 180.0,        # per square meter
        "sand": 1200.0,       # per cubic meter
        "gravel": 950.0,      # per cubic meter
    },
    "materials_markup": 1.0,
    "equipment": {
        "default": 2500.0, "crane": 18000.0, "excavator": 9500.0,
        "loader": 7500.0, "concrete_mixer": 1800.0, "scaffolding": 600.0,
        "generator": 1200.0, "welding_machine": 900.0, "boom_truck": 6500.0,
    },
    "contingency_pct": 10.0,
    "vat_pct": 0.0,
}



class CostEstimator:
    """Compute CostBreakdown from RecommendedService line items."""

    def __init__(self, settings: Settings, rates: Optional[dict] = None) -> None:
        self.settings = settings
        self._rates = rates or self._build_rate_table()
        self._service_overrides: dict[str, dict] = {}

    def _build_rate_table(self) -> dict[str, Any]:
        currency = (getattr(self.settings, "cost_currency", None) or "PHP").upper()
        return {"currency": currency, "rates": DEFAULT_RATES_PHP,
                "notes": "DPWH / DOLE 2024-2025 fallback rates; not official quotations."}

    def set_rates(self, *, currency: Optional[str] = None, rates: dict) -> None:
        if currency:
            self._rates["currency"] = currency.upper()
        self._rates["rates"] = rates

    def set_service_override(self, service_key: str, override: dict) -> None:
        self._service_overrides[service_key] = override

    def _classify(self, text: str) -> str:
        t = (text or "").lower()
        scores = {"labor": 0, "equipment": 0, "materials": 0}
        for cat, words in SERVICE_KEYWORDS.items():
            for w in words:
                if w in t:
                    scores[cat] += 1
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "materials"

    def _lookup_unit_cost(self, category: str, text: str, default: float) -> float:
        rates = self._rates["rates"]
        if category == "labor":
            table = rates.get("labor", {})
            for key, val in table.items():
                if key != "default" and key in text.lower():
                    return float(val)
            return float(table.get("default", default))
        if category == "materials":
            table = rates.get("materials", {})
            for key, val in table.items():
                if key != "default" and key in text.lower():
                    return float(val)
            return float(table.get("default", default))
        if category == "equipment":
            table = rates.get("equipment", {})
            for key, val in table.items():
                if key != "default" and key.replace("_", " ") in text.lower():
                    return float(val)
            return float(table.get("default", default))
        return float(default)

    def estimate_line(self, line: RecommendedService) -> dict:
        key = (line.service or line.id or "").strip()
        if key in self._service_overrides:
            ov = self._service_overrides[key]
            return {"category": ov.get("category", "materials"),
                    "unit_cost": float(ov.get("unit_cost", line.unit_cost or 0.0)),
                    "total_cost": float(ov.get("unit_cost", line.unit_cost or 0.0)) * float(line.quantity or 1),
                    "source": "override"}
        category = self._classify(key)
        qty = float(line.quantity or 1)
        if line.unit_cost and line.unit_cost > 0:
            unit = float(line.unit_cost)
        else:
            unit = self._lookup_unit_cost(category, key, default=0.0)
        return {"category": category, "unit_cost": unit, "total_cost": unit * qty, "source": "computed"}

    def estimate(self, services: list[RecommendedService]) -> CostBreakdown:
        if not services:
            raise CostEstimationError("No services to estimate.")
        labor = materials = equipment = 0.0
        for s in services:
            est = self.estimate_line(s)
            if est["category"] == "labor":
                labor += est["total_cost"]
            elif est["category"] == "equipment":
                equipment += est["total_cost"]
            else:
                materials += est["total_cost"]
        currency = self._rates.get("currency", "PHP")
        rates = self._rates.get("rates", DEFAULT_RATES_PHP)
        subtotal = labor + materials + equipment
        contingency_pct = float(rates.get("contingency_pct", 10.0))
        contingency = round(subtotal * (contingency_pct / 100.0), 2)
        vat_pct = float(rates.get("vat_pct", 0.0))
        pre_total = subtotal + contingency
        vat = round(pre_total * (vat_pct / 100.0), 2)
        total = round(pre_total + vat, 2)
        return CostBreakdown(currency=currency, labor=round(labor, 2), materials=round(materials, 2),
                             equipment=round(equipment, 2), subtotal=round(subtotal, 2),
                             contingency_pct=contingency_pct, contingency=contingency, total=total)

    def to_dict(self, breakdown: CostBreakdown) -> dict:
        return breakdown.model_dump()


_cost_estimator_instance: Optional[CostEstimator] = None


def get_cost_estimator(settings: Optional[Settings] = None) -> CostEstimator:
    global _cost_estimator_instance
    if _cost_estimator_instance is None:
        if settings is None:
            from app.config import get_settings
            settings = get_settings()
        _cost_estimator_instance = CostEstimator(settings)
    return _cost_estimator_instance


SERVICE_KEYWORDS = {
    "labor": ["labor", "labour", "manpower", "worker", "personnel", "technician",
              "electrician", "welder", "mason", "carpenter", "painter", "plumber",
              "foreman", "operator", "installation", "rewiring", "wiring"],
    "equipment": ["rental", "equipment", "crane", "excavator", "loader", "mixer",
                  "scaffolding", "generator", "welding machine", "boom truck",
                  "machinery", "tool"],
    "materials": ["supply", "material", "cement", "concrete", "steel", "rebar", "wire",
                  "pipe", "paint", "tile", "board", "panel", "lumber", "sand",
                  "gravel", "aggregate", "fastener", "insulation"],
}


class CostEstimationError(RuntimeError):
    pass
