@echo off
rem OSIRIS Imhotep - start backend (FastAPI + uvicorn on :8000)
rem Safe to double-click: batch files bypass the PowerShell execution policy.
cd /d "%~dp0backend"
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
pause
