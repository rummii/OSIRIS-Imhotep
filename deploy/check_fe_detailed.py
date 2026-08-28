import httpx
import re

fe = "https://osiris-frontend-890958491914.us-central1.run.app"
c = httpx.Client(timeout=30)

print("Fetching main page...")
html = c.get(fe).text

# Find all JS chunks
bundle_matches = re.findall(r'/_next/static/[^"]+\.js', html)
print(f"Found {len(bundle_matches)} JS bundles")

# Also look for CSS to be thorough
css_matches = re.findall(r'/_next/static/[^"]+\.css', html)
print(f"Found {len(css_matches)} CSS bundles")

# Check the main JS bundle (usually the first one)
if bundle_matches:
    bundle_url = fe + bundle_matches[0]
    print(f"Fetching main bundle: {bundle_url}")
    bundle_js = c.get(bundle_url).text
    
    # Check for signs of our code
    checks = [
        ("downloadSowDocx", "downloadSowDocx function"),
        ("exportSowToGdoc", "exportSowToGdoc function"),
        ("download-docx", "download-docx endpoint"),
        ("Download .docx", "button text"),
        ("ExternalLink", "ExternalLink icon (Docs button)"),
        ("Download", "Download icon (docx button)")
    ]
    
    for pattern, desc in checks:
        if pattern in bundle_js:
            print(f"✓ FOUND: {desc}")
        else:
            print(f"✗ MISSING: {desc}")
    
    # Show context around downloadSowDocx if found
    idx = bundle_js.find("downloadSowDocx")
    if idx >= 0:
        print(f"\nContext around downloadSowDocx:")
        print(bundle_js[max(0, idx-100):idx+200])
    else:
        print("\ndownloadSowDocx not found in bundle")
        
    # Show first 500 chars to see what's actually in there
    print(f"\nFirst 500 chars of bundle:")
    print(bundle_js[:500])
else:
    print("No JS bundles found!")