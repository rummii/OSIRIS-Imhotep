"""Reusable SOW data fixtures for export and route tests."""
from __future__ import annotations

from typing import Any

# Minimal SOW — just enough to exercise the happy path for all formats.
MIN_SOW: dict[str, Any] = {
    "project_title": "Minimal Test SOW",
    "site": "Test Site Alpha",
    "client": "Test Client Corp",
    "generated_at": "2025-01-15T09:00:00Z",
    "currency": "PHP",
    "executive_summary": {
        "overview": "Overview of minimal SOW.",
        "overall_condition": "Good",
    },
    "visual_findings": [],
    "recommended_services": [],
    "scope_breakdown": [],
    "schedule": [],
    "wbs_tree": {},
    "references": [],
}

# Full SOW — exercises executive summary, visual findings, recommended services,
# scope breakdown with deliverables, and the schedule / WBS tree.
FULL_SOW: dict[str, Any] = {
    "project_title": "Comprehensive Engineering Assessment — HVAC System Overhaul",
    "site": "Facility B – Level 3 Mechanical Room",
    "client": "Meridian Industrial Holdings Corp.",
    "generated_at": "2025-06-01T14:30:00Z",
    "currency": "PHP",
    "executive_summary": {
        "overview": (
            "This assessment covers the complete replacement and upgrade of the "
            "building HVAC system serving floors 2 through 6, including ductwork "
            "modifications, new AHU installation, and BMS integration."
        ),
        "overall_condition": "Poor — multiple units past useful life",
        "priority_findings": "Chiller #2 compressor failure; supply ducts on floor 4 show corrosion",
    },
    "visual_findings": [
        {
            "id": "VF-001",
            "asset": "AHU-01 (Primary Air Handler)",
            "location": "Roof Level, Unit 1",
            "condition": "Fair",
            "severity": "Medium",
            "description": "Coil fins heavily fouled; condensate pan shows sediment buildup.",
            "oem_reference": "CARRIER-40RUS-08",
            "recommended_action": "Full coil replacement and pan cleaning scheduled for Phase 2.",
        },
        {
            "id": "VF-002",
            "asset": "Chiller #2",
            "location": "Basement Plant Room",
            "condition": "Critical",
            "severity": "High",
            "description": "Compressor seized; refrigerant leak detected at evaporator bundle.",
            "oem_reference": "TRANE-CVHE-450",
            "recommended_action": "Immediate shutdown and compressor replacement required.",
        },
    ],
    "recommended_services": [
        {
            "id": "RS-001",
            "service": "HVAC System Replacement — Full",
            "asset": "AHU-01, Duct Network",
            "priority": "High",
            "quantity": 1,
            "unit": "lot",
            "unit_cost": 4_500_000.0,
            "total_cost": 4_500_000.0,
            "notes": "Includes removal of existing units, new installation, and commissioning.",
        },
        {
            "id": "RS-002",
            "service": "Chiller Compressor Replacement",
            "asset": "Chiller #2",
            "priority": "Critical",
            "quantity": 1,
            "unit": "unit",
            "unit_cost": 1_800_000.0,
            "total_cost": 1_800_000.0,
            "notes": "OEM-equivalent replacement; 12-month warranty.",
        },
        {
            "id": "RS-003",
            "service": "Ductwork Rehabilitation — Floor 4",
            "asset": "Supply/Return Ducts, Floor 4",
            "priority": "Medium",
            "quantity": 120,
            "unit": "m",
            "unit_cost": 8500.0,
            "total_cost": 1_020_000.0,
            "notes": "Replace corroded sections; re-insulate entire run.",
        },
    ],

    "scope_breakdown": [
        {
            "phase": "Phase 1 — Decommissioning",
            "work_description": "Isolate and remove Chiller #2; disconnect AHU-01 from live systems.",
            "deliverables": ["Isolation permits", "Hazardous-material survey", "Equipment removal"],
            "duration_days": 10,
            "depends_on": [],
            "sequence": 1,
        },
        {
            "phase": "Phase 2 — Structural Preparation",
            "work_description": "Install new pad foundations for replacement units; modify ceiling grid on Floor 4.",
            "deliverables": ["Poured concrete pads", "Ceiling grid modifications", "Seismic restraints"],
            "duration_days": 8,
            "depends_on": ["Phase 1 — Decommissioning"],
            "sequence": 2,
        },
        {
            "phase": "Phase 3 — Mechanical Installation",
            "work_description": "Install new AHU-01 and replacement chiller; connect ductwork and piping.",
            "deliverables": [
                "New AHU-01 in place and bolted",
                "Chiller #2 replacement commissioned",
                "All ductwork sealed and insulated",
            ],
            "duration_days": 30,
            "depends_on": ["Phase 2 — Structural Preparation"],
            "sequence": 3,
        },
        {
            "phase": "Phase 4 — BMS Integration & Testing",
            "work_description": "Connect all units to building management system; perform TAB and performance testing.",
            "deliverables": ["BMS graphics updated", "TAB report", "Performance test certificate"],
            "duration_days": 14,
            "depends_on": ["Phase 3 — Mechanical Installation"],
            "sequence": 4,
        },
        {
            "phase": "Phase 5 — Commissioning & Handover",
            "work_description": "Full-system commissioning, owner training, O&M manual delivery.",
            "deliverables": ["Commissioning report", "O&M manuals", "Training records", "As-built drawings"],
            "duration_days": 7,
            "depends_on": ["Phase 4 — BMS Integration & Testing"],
            "sequence": 5,
        },
    ],
    "schedule": [
        {"phase": "Phase 1 — Decommissioning",        "start_day": 1,  "duration_days": 10},
        {"phase": "Phase 2 — Structural Preparation",  "start_day": 11, "duration_days": 8},
        {"phase": "Phase 3 — Mechanical Installation", "start_day": 19, "duration_days": 30},
        {"phase": "Phase 4 — BMS Integration",         "start_day": 49, "duration_days": 14},
        {"phase": "Phase 5 — Commissioning",            "start_day": 63, "duration_days": 7},
    ],
    "wbs_tree": {
        "1": {"name": "Phase 1 — Decommissioning",         "level": 1, "parent": None},
        "2": {"name": "Phase 2 — Structural Preparation",  "level": 1, "parent": None},
        "3": {"name": "Phase 3 — Mechanical Installation",  "level": 1, "parent": None},
        "4": {"name": "Phase 4 — BMS Integration",          "level": 1, "parent": None},
        "5": {"name": "Phase 5 — Commissioning",            "level": 1, "parent": None},
    },
    "references": [
        {"title": "ASHRAE Standard 62.1",  "url": "https://www.ashrae.org"},
        {"title": "PH Building Code 2022",  "url": "https://www.dpwh.gov.ph"},
    ],
}



# WBS SOW with a fan-in dependency pattern (P3 depends on P1 + P2).
# Used to verify that all PredecessorLink nodes are emitted correctly.
WBS_FAN_IN_SOW: dict[str, Any] = {
    "project_title": "Fan-In WBS Test",
    "generated_at": "2025-03-01T00:00:00Z",
    "currency": "USD",
    "executive_summary": {
        "overview": "Sequential phases with fan-in.",
        "overall_condition": "N/A",
    },
    "visual_findings": [],
    "recommended_services": [],
    "scope_breakdown": [
        {
            "phase": "P1 — Site Survey",
            "work_description": "Initial site survey.",
            "deliverables": ["Survey report"],
            "duration_days": 3,
            "depends_on": [],
            "sequence": 1,
        },
        {
            "phase": "P2 — Design Phase",
            "work_description": "Engineering design.",
            "deliverables": ["Drawings"],
            "duration_days": 5,
            "depends_on": [],
            "sequence": 2,
        },
        {
            "phase": "P3 — Integration",
            "work_description": "Integration meeting.",
            "deliverables": ["Sign-off"],
            "duration_days": 2,
            "depends_on": ["P1 — Site Survey", "P2 — Design Phase"],  # fan-in: two predecessors
            "sequence": 3,
        },
        {
            "phase": "P4 — Final Review",
            "work_description": "Final review.",
            "deliverables": ["Approval"],
            "duration_days": 1,
            "depends_on": ["P3 — Integration"],
            "sequence": 4,
        },
    ],
    "schedule": [
        {"phase": "P1 — Site Survey",   "start_day": 1, "duration_days": 3},
        {"phase": "P2 — Design Phase",  "start_day": 1, "duration_days": 5},
        {"phase": "P3 — Integration",    "start_day": 6, "duration_days": 2},
        {"phase": "P4 — Final Review",  "start_day": 8, "duration_days": 1},
    ],
    "wbs_tree": {
        "1": {"name": "P1 — Site Survey",   "level": 1, "parent": None},
        "2": {"name": "P2 — Design Phase",   "level": 1, "parent": None},
        "3": {"name": "P3 — Integration",     "level": 1, "parent": None},
        "4": {"name": "P4 — Final Review",   "level": 1, "parent": None},
    },
    "references": [],
}

# WBS SOW with zero-dependency phases — verifies schedule without predecessor links.
WBS_NO_DEPS_SOW: dict[str, Any] = {
    "project_title": "No-Dependencies WBS Test",
    "generated_at": "2025-03-01T00:00:00Z",
    "currency": "EUR",
    "executive_summary": {
        "overview": "Three independent parallel phases.",
        "overall_condition": "N/A",
    },
    "visual_findings": [],
    "recommended_services": [],
    "scope_breakdown": [
        {
            "phase": "Phase A",
            "work_description": "Independent task A.",
            "deliverables": ["Deliverable A"],
            "duration_days": 4,
            "depends_on": [],
            "sequence": 1,
        },
        {
            "phase": "Phase B",
            "work_description": "Independent task B.",
            "deliverables": ["Deliverable B"],
            "duration_days": 3,
            "depends_on": [],
            "sequence": 2,
        },
        {
            "phase": "Phase C",
            "work_description": "Independent task C.",
            "deliverables": ["Deliverable C"],
            "duration_days": 5,
            "depends_on": [],
            "sequence": 3,
        },
    ],
    "schedule": [
        {"phase": "Phase A", "start_day": 1, "duration_days": 4},
        {"phase": "Phase B", "start_day": 1, "duration_days": 3},
        {"phase": "Phase C", "start_day": 1, "duration_days": 5},
    ],
    "wbs_tree": {
        "1": {"name": "Phase A", "level": 1, "parent": None},
        "2": {"name": "Phase B", "level": 1, "parent": None},
        "3": {"name": "Phase C", "level": 1, "parent": None},
    },
    "references": [],
}
