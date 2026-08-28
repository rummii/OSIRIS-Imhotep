"""Fix _sow_to_markdown field names to match the actual schema."""
from pathlib import Path

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\services\sow_service.py")
text = p.read_text(encoding="utf-8")

# VisualFinding uses 'description' + 'recommended_action', not 'observation'/'recommendation'
old_vf = '''            if vf.observation:
                lines.append(f"**Observation:** {vf.observation}")
            if vf.severity:
                lines.append(f"**Severity:** {vf.severity}")
            if vf.recommendation:
                lines.append(f"**Recommendation:** {vf.recommendation}")'''
new_vf = '''            if vf.description:
                lines.append(f"**Description:** {vf.description}")
            if vf.severity:
                lines.append(f"**Severity:** {vf.severity}")
            if vf.recommended_action:
                lines.append(f"**Recommended Action:** {vf.recommended_action}")'''
assert old_vf in text, "visual finding block not found"
text = text.replace(old_vf, new_vf)

# RecommendedService: field is 'service' (and 'asset'/'priority'), not 'service_name'/'category'
old_svc = '''            cat = svc.category if getattr(svc, "category", None) else "General"
            lines.append(
                f"- **{svc.service_name}** ({cat}) - "
                f"{sow.cost_breakdown.currency} {svc.total_cost:,.2f}"
            )'''
new_svc = '''            asset = svc.asset if getattr(svc, "asset", None) else "General"
            lines.append(
                f"- **{svc.service}** (Asset: {asset}, Priority: {svc.priority}) - "
                f"{sow.cost_breakdown.currency} {svc.total_cost:,.2f}"
            )'''
assert old_svc in text, "service block not found"
text = text.replace(old_svc, new_svc)

# ScopeItem uses 'work_description' (not 'description')
old_scope = '''            if scope.description:
                lines.append(f"\\n{scope.description}\\n")'''
new_scope = '''            if scope.work_description:
                lines.append(f"\\n{scope.work_description}\\n")'''
assert old_scope in text, "scope block not found"
text = text.replace(old_scope, new_scope)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
