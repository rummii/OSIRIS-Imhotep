@echo off
rem OSIRIS Imhotep - restart backend cleanly.
rem Kills whatever holds port 8000, then opens dev-backend.cmd in a new window.
rem Safe to double-click anytime, even if the backend is already running.
set "ROOT=%~dp0"

echo [restart-backend] Freeing port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    echo [restart-backend] Killing PID %%p (old backend)
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [restart-backend] Starting dev-backend.cmd...
start "" "%ROOT%dev-backend.cmd"
echo [restart-backend] Done. Backend window opened on :8000.
