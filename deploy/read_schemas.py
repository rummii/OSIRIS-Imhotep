"""Read and print the schema definitions."""
from pathlib import Path
import re

text = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend\app\models\schemas.py").read_text()

# Find VisualFinding, RecommendedService, ScopeItem
for cls in ["VisualFinding", "RecommendedService", "ScopeItem", "ExecutiveSummary"]:
    pattern = rf"class {cls}\(BaseModel\):(.*?)(?=class |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        print(f"=== {cls} ===")
        print(m.group()[:600])
        print()
