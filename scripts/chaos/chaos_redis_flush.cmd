@echo off
setlocal
set "DC_CMD=%DOCKER_COMPOSE%"
if "%DC_CMD%"=="" set "DC_CMD=docker compose"

set "REDIS_CMD=redis-cli"

for /f "delims=" %%i in ('%DC_CMD% ps -q redis') do set "REDIS_ID=%%i"
if "%REDIS_ID%"=="" (
  echo [chaos][WARN] redis container not running, skipping
  exit /b 0
)

echo [chaos] flushing redis cache
%DC_CMD% exec -T redis %REDIS_CMD% FLUSHALL
if errorlevel 1 (
  echo [chaos][ERROR] redis flush failed
  exit /b 1
)

timeout /t 5 /nobreak >NUL

echo [chaos] running legal gate smoke (entitlements recompute)
call "%~dp0..\smoke_legal_gate.cmd"
if errorlevel 1 (
  echo [chaos][ERROR] legal gate smoke failed
  exit /b 1
)

echo [chaos] running billing smoke (pricing/version cache reload)
call "%~dp0..\smoke_billing_v14.cmd"
if errorlevel 1 (
  echo [chaos][ERROR] billing smoke failed
  exit /b 1
)

echo [chaos] redis flush scenario PASS
exit /b 0
