@echo off
setlocal

if "%1"=="/h" goto :help
if "%1"=="/help" goto :help

if "%COMPOSE_FILE%"=="" (
  set COMPOSE_FILE=docker-compose.yml
)

echo Running core-api tests inside the container...
docker compose exec -T core-api pytest -q %*
exit /b %ERRORLEVEL%

:help
echo Usage: scripts\test_core_api.cmd [pytest args]
echo.
echo Runs pytest inside the core-api container to avoid local dependency issues.
endlocal
