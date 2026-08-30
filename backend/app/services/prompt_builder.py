"""Prompt & context assembly for the DeepSeek SOW generation call.

Kept deliberately separate from the Gemini HTTP layer so that:
  * the system prompt can evolve independently of the transport, and
  * context documents from any ContextProvider (RAG, static SOPs, etc.)
    are injected here — the model and the routes never see the plumbing.

The prompt is built in two halves:

* ``system`` — role definition, output contract, cost/severity conventions,
  grounding instructions, and any RAG context documents.
* ``user``   — the engineer's field notes + a media manifest listing every
  uploaded image / sampled video frame the model is being shown.
"""
from __future__ import annotations

from app.core.context_provider import ContextDocument

# ---------------------------------------------------------------------------
# Static prompt fragments
# ---------------------------------------------------------------------------

ROLE_BLOCK = """You are OSIRIS, a senior licensed facilities engineering consultant.
You produce professional, client-ready Scope of Work (SOW) documents from
engineer field notes about civil, structural, MEP, and industrial assets."""

OUTPUT_CONTRACT = """OUTPUT CONTRACT — respond with ONLY a single valid JSON object (no markdown
fences, no extra text) containing the Scope of Work DATA. Fill in exactly this
structure, replacing every placeholder value with real content:

{
  "project_title": "AHU-1 Vibration Investigation & Drive Belt Replacement",
  "site": "Plant 2 - Mechanical Room",
  "client": "ACME Manufacturing",
  "generated_at": "2025-01-15",
  "currency": "PHP",
  "executive_summary": {
    "overview": "2-4 sentence summary of the engagement and recommended work.",
    "overall_condition": "Fair",
    "priority_findings": "Urgent: replace the worn drive belt and inspect motor mounts."
  },
  "visual_findings": [
    {
      "id": "VF-01",
      "asset": "Air Handling Unit AHU-1",
      "location": "Supply fan section",
      "condition": "Worn / deteriorated",
      "severity": "Major",
      "description": "Describe what was observed and which media filename supports it.",
      "oem_reference": "OEM model or standard reference, or null",
      "recommended_action": "Specific corrective action."
    }
  ],
  "recommended_services": [
    {
      "id": "S-01",
      "service": "Replace supply fan drive belt",
      "asset": "AHU-1",
      "priority": "High",
      "quantity": 2,
      "unit": "ea",
      "unit_cost": 4800.00,
      "total_cost": 9600.00,
      "notes": "Use OEM-specified belt; include tensioning."
    }
  ],
  "scope_breakdown": [
    {
      "phase": "Phase 1 - Investigation & Mobilization",
      "work_description": "What happens in this phase.",
      "deliverables": ["Findings report", "Material list"],
      "duration_days": 5,
      "depends_on": [],
      "sequence": 1
    },
    {
      "phase": "Phase 2 - Remediation Works",
      "work_description": "Describe Phase 2 tasks.",
      "deliverables": ["Completed remediation report"],
      "duration_days": 10,
      "depends_on": ["Phase 1 - Investigation & Mobilization"],
      "sequence": 2
    }
  ],
  "cost_breakdown": {
    "labor": 65000.00,
    "materials": 19000.00,
    "equipment": 8400.00,
    "subtotal": 92400.00,
    "contingency_pct": 10,
    "contingency": 9240.00,
    "total": 101640.00
  }
}

RULES:
- Output the DATA. Do NOT repeat this template's placeholder text, and never
  include JSON Schema keywords as keys: no "type", "properties", "required",
  "items", or "value" fields anywhere in the output.
- Use only real evidence from the engineer's notes and vision analysis. Use
  null for anything not verifiable; do not invent specs or measurements.
- Severity vocabulary: Critical | Major | Moderate | Minor | Info.
  Priority vocabulary: Urgent | High | Medium | Low.
- Keep the cost math consistent: subtotal = labor + materials + equipment;
  contingency = subtotal * contingency_pct / 100; total = subtotal + contingency.
- Every array may be empty if there is genuinely no data, but prefer to include
  real entries derived from the supplied evidence.
- For scope_breakdown, include depends_on (array of phase names this phase relies on;
  leave empty for the first phase) and sequence (1-based integer; lower = earlier).
  Every phase after the first should list its predecessors in depends_on."""

EVIDENCE_BLOCK = """EVIDENCE RULES — you may ONLY report findings explicitly stated in the
engineer's notes or visual evidence supplied by the vision analyst. Never invent damage, inspections, or specifications.
Distinguish clearly between what was OBSERVED and what is a RECOMMENDATION.
State when an on-site inspection or manufacturer verification is required."""

CONTEXT_BLOCK = """SUPPLEMENTAL CONTEXT — the following documents were retrieved from company
internal systems (price books, SOPs, standards). Prefer these figures for
pricing and methods when applicable, and cite the source id in service notes:

{context_docs}"""


class PromptBuilder:
    """Assembles system + user prompts for the SOW generation call."""

    def build_system_prompt(
        self,
        context_docs: list[ContextDocument] | None = None,
    ) -> str:
        parts: list[str] = [ROLE_BLOCK, OUTPUT_CONTRACT]
        parts.append(EVIDENCE_BLOCK)

        if context_docs:
            rendered = "\n".join(
                f"- [{doc.source}] {doc.content}" for doc in context_docs if doc.content
            )
            parts.append(CONTEXT_BLOCK.format(context_docs=rendered))

        return "\n\n".join(parts)

    def build_user_prompt(
        self,
        notes: str = "",
        site: str = "",
        client: str = "",
        visual_evidence: str = "",
        spatial_lines: list[str] | None = None,
    ) -> str:
        meta_lines = []
        if site:
            meta_lines.append(f"Site / facility: {site}")
        if client:
            meta_lines.append(f"Client: {client}")

        notes_block = (
            f"ENGINEER FIELD NOTES:\n{notes.strip()}"
            if notes.strip()
            else "ENGINEER FIELD NOTES: (none provided)"
        )
        evidence_block = (
            f"GEMINI VISION EVIDENCE:\n{visual_evidence.strip()}"
            if visual_evidence.strip()
            else "GEMINI VISION EVIDENCE: No media was supplied."
        )

        spatial_block = ""
        if spatial_lines:
            spatial_block = "\n\nSPATIAL CONTEXT (from uploaded media EXIF / GPS):\n" + "\n".join(spatial_lines)

        header = "\n".join(meta_lines) + "\n\n" if meta_lines else ""
        return (
            f"{header}{notes_block}\n\n{evidence_block}{spatial_block}\n\n"
            "Generate the SOW JSON per the OUTPUT CONTRACT. Be specific, use only "
            "the supplied evidence, and stay "
            "within the agreed severity/priority vocabulary."
        )
