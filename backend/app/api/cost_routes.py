"""Cost estimation HTTP routes.

Endpoints
---------
POST /api/cost/estimate      - Compute CostBreakdown from line items (no LLM)
GET  /api/cost/rates         - Inspect current rate catalog (admin)
POST /api/cost/rates         - Replace rate catalog (admin)
GET  /api/cost/overrides     - List per-service overrides (admin)
POST /api/cost/overrides     - Set per-service override (admin)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.dependencies import get_current_user, require_superadmin
from app.models.schemas import RecommendedService
from app.services.audit_service import AuditService
from app.services.cost_estimator import (
    CostEstimationError,
    CostEstimator,
    get_cost_estimator,
)

logger = logging.getLogger("osiris.cost.routes")
router = APIRouter(prefix="/cost", tags=["cost"])


class EstimateRequest(BaseModel):
    services: list[RecommendedService] = Field(default_factory=list)
    currency: Optional[str] = None  # override the default currency for this call only


class EstimateResponse(BaseModel):
    currency: str
    labor: float
    materials: float
    equipment: float
    subtotal: float
    contingency_pct: float
    contingency: float
    total: float
    line_classification: list[dict] = Field(default_factory=list)


@router.post("/estimate", response_model=EstimateResponse)
def estimate(
    payload: EstimateRequest,
    current_user: dict = Depends(get_current_user),
) -> EstimateResponse:
    """Compute a CostBreakdown for the provided SOW line items.

    Auth: any authenticated user.
    """
    settings = get_settings()
    estimator = get_cost_estimator(settings)
    if payload.currency:
        estimator._rates["currency"] = payload.currency.upper()  # type: ignore[attr-defined]
    try:
        breakdown = estimator.estimate(payload.services)
    except CostEstimationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    classifications = [estimator.estimate_line(s) for s in payload.services]

    try:
        AuditService(settings).log(
            "cost_estimate",
            user=current_user,
            target_type="cost",
            target_id="estimate",
            outcome="success",
            detail=f"lines={len(payload.services)} total={breakdown.total:.2f} {breakdown.currency}",
        )
    except Exception:
        pass  # never block the response on audit

    return EstimateResponse(
        currency=breakdown.currency,
        labor=breakdown.labor,
        materials=breakdown.materials,
        equipment=breakdown.equipment,
        subtotal=breakdown.subtotal,
        contingency_pct=breakdown.contingency_pct,
        contingency=breakdown.contingency,
        total=breakdown.total,
        line_classification=classifications,
    )


@router.get("/rates")
def get_rates(_: dict = Depends(require_superadmin)) -> dict:
    settings = get_settings()
    estimator = get_cost_estimator(settings)
    return {
        "currency": estimator._rates.get("currency", "PHP"),  # type: ignore[attr-defined]
        "rates": estimator._rates.get("rates", {}),  # type: ignore[attr-defined]
        "notes": estimator._rates.get("notes", ""),  # type: ignore[attr-defined]
    }


class RatesUpdateRequest(BaseModel):
    currency: Optional[str] = None
    rates: dict


@router.post("/rates")
def update_rates(
    payload: RatesUpdateRequest, current_user: dict = Depends(require_superadmin)
) -> dict:
    settings = get_settings()
    estimator = get_cost_estimator(settings)
    estimator.set_rates(currency=payload.currency, rates=payload.rates)
    try:
        AuditService(settings).log(
            "cost_rates_update",
            user=current_user,
            target_type="cost",
            target_id="rates",
            outcome="success",
            detail=f"currency={payload.currency or 'unchanged'}",
        )
    except Exception:
        pass
    return {"ok": True, "currency": estimator._rates.get("currency", "PHP")}  # type: ignore[attr-defined]


@router.get("/overrides")
def list_overrides(_: dict = Depends(require_superadmin)) -> dict:
    settings = get_settings()
    estimator = get_cost_estimator(settings)
    return {"overrides": estimator._service_overrides}  # type: ignore[attr-defined]


class OverrideRequest(BaseModel):
    service_key: str
    category: str = "materials"
    unit_cost: float = 0.0


@router.post("/overrides")
def set_override(
    payload: OverrideRequest, current_user: dict = Depends(require_superadmin)
) -> dict:
    settings = get_settings()
    estimator = get_cost_estimator(settings)
    estimator.set_service_override(
        payload.service_key,
        {"category": payload.category, "unit_cost": payload.unit_cost},
    )
    try:
        AuditService(settings).log(
            "cost_override_set",
            user=current_user,
            target_type="cost",
            target_id=payload.service_key,
            outcome="success",
            detail=f"category={payload.category} unit_cost={payload.unit_cost}",
        )
    except Exception:
        pass
    return {"ok": True, "service_key": payload.service_key}
