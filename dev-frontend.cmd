dev@echo off
rem OSIRIS Imhotep - start frontend (Next.js dev server on :3000)
rem npm.cmd is used because the PowerShell execution policy blocks "npm" (a .ps1).
cd /d "%~dp0frontend"
npm.cmd run dev
pause
