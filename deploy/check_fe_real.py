import httpx
import re
import sys

fe = "https://osiris-frontend-890958491914.us-central1.run.app"
c = httpx.Client(timeout=30, follow_redirects=True)

print("=== Checking live frontend ===")
print(f"URL: {fe}\n")

# Get main page
html = c.get(fe + "/").text
print(f"Main page size: {len(html)} bytes")

# Find all script chunks
chunks = re.findall(r'/_next/static/chunks/[^"]+\.js', html)
print(f"Found {len(chunks)} chunk URLs in main page")

# Fetch all chunks and search
found = False
for chunk_path in chunks[:20]:  # check up to 20 chunks
    chunk_url = fe + chunk_path
    js = c.get(chunk_url).text
    if 'downloadSowDocx' in js or 'download-docx' in js:
        print(f"\n✓ FOUND in chunk: {chunk_path}")
        idx = js.find('downloadSowDocx')
        if idx >= 0:
            print(f"  Context: ...{js[max(0,idx-50):idx+200]}...")
        found = True
        break

if not found:
    print("\n✗ downloadSowDocx NOT FOUND in any chunk")
    print("  This means the deployed image is STALE (missing the new code)")
    print("  Need to force a fresh rebuild + redeploy")

# Also check what the app's next.config.js redirects look like
print("\n=== Checking next.config.js rewrites ===")
config_match = re.search(r'rewrites\s*[:=]', html)
if config_match:
    print("  rewrites found in HTML (likely compiled into client config)")

# Check documents page specifically
print("\n=== Checking /documents page ===")
try:
    docs_html = c.get(fe + "/documents").text
    print(f"  Size: {len(docs_html)} bytes")
    # Look for auth-redirect logic
    if 'router.replace' in docs_html or '/login' in docs_html:
        print("  Has auth redirect logic")
except Exception as e:
    print(f"  Error: {e}")

# Check API client
print("\n=== Checking API client file (chunks/app) ===")
app_chunks = [c for c in chunks if 'app' in c or 'documents' in c]
for chunk in app_chunks[:5]:
    js = c.get(fe + chunk).text
    if 'listSowDocuments' in js or 'createSowDocument' in js:
        print(f"  API client in: {chunk}")
        if 'localhost' in js:
            print(f"  !! STILL REFERENCES LOCALHOST (will fail to save)")
        else:
            print(f"  ✓ No localhost references")
        break
