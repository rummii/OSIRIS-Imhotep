# Restart backend with the PHP currency changes.
$ErrorActionPreference = "Continue"
Set-Location "C:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\backend"
$log = "php_restart.log"

$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conns) { $conns.OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Start-Sleep -Seconds 2 }

$p = Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000", "--log-level", "info" `
    -WorkingDirectory (Get-Location) -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "uvicorn_out.log" -RedirectStandardError "uvicorn_err.log"
"STARTED_PID $($p.Id)" | Out-File $log -Encoding utf8

for ($i = 0; $i -lt 30; $i++) {
    try {
        $h = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 3
        if ($h.StatusCode -eq 200) { "HEALTH_OK" | Out-File $log -Append -Encoding utf8; break }
    } catch {}
    Start-Sleep -Seconds 1
}
"DONE" | Out-File $log -Append -Encoding utf8
