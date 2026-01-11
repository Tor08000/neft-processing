@echo off
setlocal
set "DC_CMD=%DOCKER_COMPOSE%"
if "%DC_CMD%"=="" set "DC_CMD=docker compose"
set "HEALTH_URL=http://localhost/api/core/health"

echo [chaos] stopping postgres via %DC_CMD%
%DC_CMD% stop postgres
if errorlevel 1 (
  echo [chaos][ERROR] failed to stop postgres
  exit /b 1
)

timeout /t 15 /nobreak >NUL

echo [chaos] starting postgres via %DC_CMD%
%DC_CMD% start postgres
if errorlevel 1 (
  echo [chaos][ERROR] failed to start postgres
  exit /b 1
)

timeout /t 15 /nobreak >NUL

echo [chaos] checking core-api health
curl -fsS %HEALTH_URL% >NUL
if errorlevel 1 (
  echo [chaos][ERROR] core-api health check failed
  exit /b 1
)

echo [chaos] running legal gate smoke to validate entitlements
call "%~dp0..\smoke_legal_gate.cmd"
if errorlevel 1 (
  echo [chaos][ERROR] legal gate smoke failed
  exit /b 1
)

echo [chaos] postgres restart scenario PASS
exit /b 0
