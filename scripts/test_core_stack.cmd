@echo off
setlocal enabledelayedexpansion

REM ==========================================
REM Core stack tests via docker compose
REM ==========================================

set "COMPOSE_FILE=docker-compose.yml"
set "DB_SERVICE=postgres"
set "REDIS_SERVICE=redis"
set "MINIO_SERVICE=minio"

echo [core-stack] Starting dependencies...
docker compose -f %COMPOSE_FILE% up -d %DB_SERVICE% %REDIS_SERVICE% %MINIO_SERVICE%
if errorlevel 1 exit /b 1

echo [core-stack] Waiting for postgres health...
set /a retries=30
:wait_pg
docker compose -f %COMPOSE_FILE% ps --services --filter "status=running" | findstr /I /C:"%DB_SERVICE%" >nul
if errorlevel 1 (
    echo Postgres container not running.
    exit /b 1
)
docker compose -f %COMPOSE_FILE% exec -T %DB_SERVICE% pg_isready -U neft >nul 2>&1
if %errorlevel%==0 goto run_tests
set /a retries-=1
if %retries% LEQ 0 (
    echo Postgres did not become ready.
    exit /b 1
)
timeout /t 2 >nul
goto wait_pg

:run_tests
echo [core-stack] Running legal gate tests...
docker compose -f %COMPOSE_FILE% run --rm core-api pytest -q app/tests/test_legal_gate.py
if errorlevel 1 exit /b 1

echo [core-stack] Running pricing entitlements tests...
docker compose -f %COMPOSE_FILE% run --rm core-api pytest -q app/tests/test_entitlements_pricing_versions.py
if errorlevel 1 exit /b 1

if /I "%1"=="--full" (
    echo [core-stack] Running full processing-core test suite...
    docker compose -f %COMPOSE_FILE% run --rm core-api pytest -q app/tests
    if errorlevel 1 exit /b 1
)

echo [core-stack] PASS
endlocal
