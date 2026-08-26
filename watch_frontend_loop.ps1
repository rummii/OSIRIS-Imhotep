# OSIRIS Imhotep — frontend self-healing watchdog LOOP.
# Runs forever: every 30s checks if Next.js dev is on :3000 and starts it if not.
$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep"
$watchLog = Join-Path $root "watch_frontend_loop.log"

while ($true) {
    $listening = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
    if (-not $listening) {
        Remove-Item "$root\frontend\next_out.log", "$root\frontend\next_err.log" -Force -ErrorAction SilentlyContinue
        try {
            Start-Process -FilePath "node" `
                -ArgumentList "node_modules\next\dist\bin\next", "dev", "-p", "3000" `
                -WorkingDirectory "$root\frontend" -WindowStyle Hidden `
                -RedirectStandardOutput "$root\frontend\next_out.log" `
                -RedirectStandardError "$root\frontend\next_err.log" `
                -ErrorAction Stop | Out-Null
            "$(Get-Date -Format 'HH:mm:ss') STARTED" | Out-File $watchLog -Append -Encoding utf8
        } catch {
            "$(Get-Date -Format 'HH:mm:ss') FAIL $($_.Exception.Message)" | Out-File $watchLog -Append -Encoding utf8
        }
    }
    Start-Sleep -Seconds 30
}
