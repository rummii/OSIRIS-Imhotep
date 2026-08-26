"""Live probe: call the Gemini API with the configured key to check quota/limit status."""
import os, sys
from pathlib import Path

root = Path(__file__).resolve().parent
env_path = root / ".env"
key = ""
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("GEMINI_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

print(f"KEY_FOUND={bool(key)}")
print(f"KEY_PREFIX={key[:8]}..." if len(key) > 8 else "KEY_TOO_SHORT")

if not key:
    print("RESULT: NO_KEY")
    sys.exit(2)

try:
    from google import genai
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with the single word: OK",
    )
    print("RESULT: SUCCESS")
    print("TEXT:", (resp.text or "").strip()[:80])
    sys.exit(0)
except Exception as exc:
    msg = str(exc)
    print("RESULT: FAILURE")
    print("ERROR:", msg[:2000])
    if any(t in msg.upper() for t in ("429", "RESOURCE_EXHAUSTED", "RATE", "QUOTA", "LIMIT")):
        print("VERDICT: GEMINI_QUOTA_LIMIT_REACHED")
    elif any(t in msg.upper() for t in ("403", "PERMISSION_DENIED", "API_KEY")):
        print("VERDICT: GEMINI_KEY_INVALID_OR_DENIED")
    else:
        print("VERDICT: OTHER_ERROR")
    sys.exit(1)
