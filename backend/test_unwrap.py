"""Unit test for DeepSeekService._unwrap_schema_echo (no network)."""
import sys
import traceback

from app.services.deepseek_service import DeepSeekService


def main() -> int:
    try:
        # Captured real DeepSeek schema-echo shape from production debugging.
        sample = {
            "type": "OBJECT",
            "properties": {
                "project_title": {"type": "STRING", "value": "Roof Repair"},
                "site": {"type": "STRING", "value": None},
                "client": {"type": "STRING", "value": "ACME"},
                "generated_at": {"type": "STRING", "value": "2025-01-15"},
                "currency": {"type": "STRING", "value": "PHP"},
                "executive_summary": {
                    "type": "OBJECT",
                    "properties": {
                        "overview": {"type": "STRING", "value": "Overview text"},
                        "overall_condition": {"type": "STRING", "value": "Fair"},
                    },
                    "required": ["overview"],
                },
                "visual_findings": {
                    "type": "ARRAY",
                    "items": {"type": "OBJECT", "properties": {}},
                },
                "recommended_services": {
                    "type": "ARRAY",
                    "items": {"type": "OBJECT", "properties": {}},
                },
                "scope_breakdown": {
                    "type": "ARRAY",
                    "items": {"type": "OBJECT", "properties": {}},
                },
                "cost_breakdown": {
                    "type": "OBJECT",
                    "properties": {
                        "labor": {"type": "NUMBER", "value": 1000},
                        "materials": {"type": "NUMBER", "value": 500},
                    },
                    "required": ["labor"],
                },
            },
            "required": ["project_title"],
        }

        out = DeepSeekService._unwrap_schema_echo(sample)
        print("UNWRAP:", out)
        assert out["project_title"] == "Roof Repair"
        assert out["executive_summary"]["overview"] == "Overview text"
        assert out["executive_summary"]["overall_condition"] == "Fair"
        assert out["cost_breakdown"]["labor"] == 1000
        assert out["site"] is None
        assert out["visual_findings"] == []
        # Non-echo payloads must pass through untouched.
        normal = {"project_title": "x", "recommended_services": []}
        assert DeepSeekService._unwrap_schema_echo(normal) == normal
        print("UNWRAP_OK")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
