@echo off
setlocal

if "%~1"=="/h" goto :help
if "%~1"=="/help" goto :help

echo [selftest] Checking core-api imports against requirements...
python scripts\check_imports.py
if errorlevel 1 exit /b %ERRORLEVEL%

echo [selftest] Running core-api tests in container...
call scripts\test_core_api.cmd %*
exit /b %ERRORLEVEL%

:help
echo Usage: selftest.cmd [pytest args]
echo.
echo Runs dependency import checks and then executes core-api pytest in docker compose.
endlocal
