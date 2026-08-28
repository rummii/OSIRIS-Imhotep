import httpx

fe = "https://osiris-frontend-890958491914.us-central1.run.app"
be = "https://osiris-imhotep-890958491914.europe-west1.run.app"

c = httpx.Client(timeout=30)
html = c.get(fe).text
# Find JS bundle links
import re
bundles = re.findall(r'/_next/static/[^"]+\.js', html)
print("JS bundles found:", len(bundles))
if bundles:
    js = c.get(fe + bundles[0]).text
    has_btn = "download-docx" in js
    print("download-docx in bundle:", has_btn)
    # Also check API client
    apis = [b for b in bundles if "api" in b]
    if apis:
        js2 = c.get(fe + apis[0]).text
        print("downloadSowDocx in api bundle:", "downloadSowDocx" in js2)
        # Print the function definition
        idx = js2.find("downloadSowDocx")
        if idx >= 0:
            print("Context:", js2[max(0,idx-50):idx+150])
