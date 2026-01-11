@echo off
setlocal enabledelayedexpansion

set TEST_TARGET=platform/processing-core/app/tests/test_entitlements_pricing_versions.py
if /I "%1"=="all" (
  set TEST_TARGET=platform/processing-core/app/tests
)

docker compose up -d postgres redis minio
if errorlevel 1 exit /b 1

set /a TRIES=0
:wait_postgres
for /f "usebackq delims=" %%c in (`docker compose ps -q postgres`) do set PG_ID=%%c
if not defined PG_ID (
  set /a TRIES+=1
  if !TRIES! geq 60 goto :postgres_timeout
  timeout /t 2 >nul
  goto :wait_postgres
)
for /f "usebackq delims=" %%s in (`docker inspect -f "{{.State.Health.Status}}" !PG_ID!`) do set PG_STATUS=%%s
if /I "!PG_STATUS!"=="healthy" goto :postgres_ready
set /a TRIES+=1
if !TRIES! geq 60 goto :postgres_timeout
timeout /t 2 >nul
goto :wait_postgres

:postgres_timeout
echo Postgres did not become healthy in time.
exit /b 1

:postgres_ready
docker compose run --rm core-api pytest -q %TEST_TARGET%
exit /b %errorlevel%
