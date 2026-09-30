@echo off
setlocal
set "ROOT=%~dp0.."
set "BIN=%ROOT%\.tools\pgsql\bin"
set "DATA=%ROOT%\.tools\pgdata"

if not exist "%BIN%\pg_ctl.exe" (
  echo PostgreSQL binaries missing. Expected: %BIN%\pg_ctl.exe
  exit /b 1
)

if not exist "%DATA%\PG_VERSION" (
  echo Postgres data directory not initialized: %DATA%
  exit /b 1
)

"%BIN%\pg_ctl.exe" status -D "%DATA%" >nul 2>&1
if errorlevel 1 (
  echo Starting local PostgreSQL...
  "%BIN%\pg_ctl.exe" -D "%DATA%" -l "%DATA%\server.log" -o "-p 5432" start
) else (
  echo Local PostgreSQL already running.
)
