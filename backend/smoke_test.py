"""Smoke test: verify all modules import, routes exist, SOW coercion works,
prompts assemble for the DeepSeek + Gemini Vision pipeline, and the
missing-key guards fire deterministically (no network calls)."""
import sys
import traceback


def main() -> int:
    try:
        from app.api.routes import router
        from app.config import Settings, get_settings
        from app.models.schemas import SowResponse, coerce_sow_payload
        from app.services.deepseek_service import DeepSeekAnalysisError, DeepSeekService
        from app.services.gdoc_service import GdocNotConfiguredError, GoogleDocsService
        from app.services.gemini_vision_service import GeminiVisionError, GeminiVisionService
        from app.services.prompt_builder import PromptBuilder
        from app.services.rag_provider import get_context_provider

        settings = get_settings()
        provider = get_context_provider(settings)
        print(f"IMPORTS_OK provider={provider.name}")

        routes = sorted(r.path for r in router.routes)
        print("ROUTES:", routes)
        assert routes == ["/health", "/sow/export-gdoc", "/sow/generate"], routes

        # --- missing-key guards (deterministic, no network) -------------------
        try:
            DeepSeekService(Settings(_env_file=None, deepseek_api_key=""))
            raise AssertionError("DeepSeekService should reject a missing key")
        except DeepSeekAnalysisError:
            pass

        try:
            GeminiVisionService(Settings(_env_file=None, gemini_api_key=""))
            raise AssertionError("GeminiVisionService should reject a missing key")
        except GeminiVisionError:
            pass

        try:
            GoogleDocsService(Settings(_env_file=None))
            raise AssertionError("GoogleDocsService should reject missing credentials")
        except GdocNotConfiguredError:
            pass
        print("MISSING_KEY_GUARDS_OK")

        # --- SOW coercion -----------------------------------------------------
        sample = {
            "project_title": "Test",
            "executive_summary": {"overview": "o", "overall_condition": "Fair"},
            "visual_findings": [],
            "recommended_services": [
                {"id": "S1", "service": "Replace belt", "asset": "AHU-1", "priority": "High",
                 "quantity": "2", "unit": "ea", "unit_cost": "150", "total_cost": None}
            ],
            "scope_breakdown": [],
            "cost_breakdown": {"labor": 1000, "materials": 500},
        }
        sow: SowResponse = coerce_sow_payload(sample)
        assert sow.cost_breakdown.total == 1650.0, sow.cost_breakdown.total
        assert sow.recommended_services[0].total_cost == 300.0
        print("COERCE_OK total=1650.0 svc_total=300.0")

        # --- prompts ----------------------------------------------------------
        pb = PromptBuilder()
        sp = pb.build_system_prompt([])
        up = pb.build_user_prompt(
            notes="AHU-1 vibrating",
            site="Plant 2",
            client="ACME",
            visual_evidence="Supply fan belt worn; casing corroded at base.",
        )
        assert "OUTPUT CONTRACT" in sp
        assert "AHU-1" in up
        assert "GEMINI VISION EVIDENCE" in up
        assert "Supply fan belt worn" in up
        print("PROMPT_OK")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

