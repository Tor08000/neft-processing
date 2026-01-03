@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ==========================================
REM Trust Gates: CI-parity local checks
REM ==========================================

set "DATABASE_URL_TEST=postgresql+psycopg://neft:neft@localhost:5432/neft"

echo [Trust Gates] Starting Postgres...
docker compose -f docker-compose.test.yml --profile test up -d postgres
if errorlevel 1 exit /b 1

echo [Trust Gates] Running migrations...
docker compose -f docker-compose.test.yml --profile test run --rm core-api alembic upgrade head
if errorlevel 1 exit /b 1

echo [Trust Gates] Checking WORM triggers...
docker compose -f docker-compose.test.yml --profile test exec -T postgres psql -U neft -d neft -f scripts/ci/check_worm_triggers.sql
if errorlevel 1 exit /b 1

echo [Trust Gates] Running trust gate tests...
pytest platform/processing-core/app/tests/test_trust_gates.py
if errorlevel 1 exit /b 1

echo [Trust Gates] OK
endlocal
