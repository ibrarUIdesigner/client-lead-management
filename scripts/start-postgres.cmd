@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure-postgres.ps1"
exit /b %ERRORLEVEL%
