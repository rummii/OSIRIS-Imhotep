# OSIRIS Imhotep — backend self-healing watchdog LOOP.
# Runs forever: every 30s checks if uvicorn is on :8000 and starts it if not.
# Started as an independent process (survives shell resets) and via a
# logon-triggered scheduled task (survives reboots).
$ErrorActionPreference = "SilentlyContinue"
$root = "C:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep"
$watchLog = Join-Path $root "watch_backend_loop.log"
$python = "$root\backend\.venv\Scripts\python.exe"

while ($true) {
    $listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if (-not $listening) {
        Remove-Item "$root\backend\uvicorn_out.log", "$root\backend\uvicorn_err.log" -Force -ErrorAction SilentlyContinue
        try {
            Start-Process -FilePath $python `
                -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "info" `
                -WorkingDirectory "$root\backend" -WindowStyle Hidden `
                -RedirectStandardOutput "$root\backend\uvicorn_out.log" `
                -RedirectStandardError "$root\backend\uvicorn_err.log" `
                -ErrorAction Stop | Out-Null
            "$(Get-Date -Format 'HH:mm:ss') STARTED" | Out-File $watchLog -Append -Encoding utf8
        } catch {
            "$(Get-Date -Format 'HH:mm:ss') FAIL $($_.Exception.Message)" | Out-File $watchLog -Append -Encoding utf8
        }
    }
    Start-Sleep -Seconds 30
}
