@echo off
setlocal

if "%1"=="/h" goto :help
if "%1"=="/help" goto :help

if "%COMPOSE_FILE%"=="" (
  set COMPOSE_FILE=docker-compose.yml
)

echo Running auth-host tests inside the container...
docker compose exec -T auth-host pytest -q %*
exit /b %ERRORLEVEL%

:help
echo Usage: scripts\test_auth_host.cmd [pytest args]
echo.
echo Runs pytest inside the auth-host container to avoid local dependency issues.
endlocal
