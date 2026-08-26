# Final preview check: frontend, proxy, and a real notes-only SOW generation
# through the Next.js proxy (browser -> :3000 -> :8000).
$log = "preview_check.log"
"PREVIEW_CHECK_START" | Out-File $log -Encoding utf8

try {
    $r = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 10
    "FRONTEND_3000:" + $r.StatusCode | Out-File $log -Append -Encoding utf8
} catch { "FRONTEND_3000:DOWN " + $_.Exception.Message | Out-File $log -Append -Encoding utf8 }

try {
    $r2 = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -UseBasicParsing -TimeoutSec 10
    "PROXY_HEALTH:" + $r2.StatusCode | Out-File $log -Append -Encoding utf8
} catch { "PROXY_HEALTH:DOWN " + $_.Exception.Message | Out-File $log -Append -Encoding utf8 }

# Real SOW generation via the proxy (DeepSeek only, no media)
try {
    $form = @{ notes = "Air Handling Unit AHU-1 reports excessive vibration and a worn drive belt. Inspect and quote replacement."; site = "Plant 2"; client = "ACME" }
    $r3 = Invoke-WebRequest -Uri "http://localhost:3000/api/sow/generate" -Method Post -Body $form -UseBasicParsing -TimeoutSec 180
    $body = $r3.Content | ConvertFrom-Json
    "GENERATE_STATUS:" + $r3.StatusCode | Out-File $log -Append -Encoding utf8
    "SOW_TITLE:" + $body.sow.project_title | Out-File $log -Append -Encoding utf8
    "FINDINGS:" + $body.sow.visual_findings.Count | Out-File $log -Append -Encoding utf8
    "SERVICES:" + $body.sow.recommended_services.Count | Out-File $log -Append -Encoding utf8
    "TOTAL:" + $body.sow.cost_breakdown.total | Out-File $log -Append -Encoding utf8
} catch { "GENERATE_ERROR:" + $_.Exception.Message | Out-File $log -Append -Encoding utf8 }

"PREVIEW_CHECK_DONE" | Out-File $log -Append -Encoding utf8
