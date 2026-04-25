@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"
if "%NEFT_BOOTSTRAP_ADMIN_EMAIL%"=="" set "NEFT_BOOTSTRAP_ADMIN_EMAIL=admin@neft.local"
if "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"=="" set "NEFT_BOOTSTRAP_ADMIN_PASSWORD=Neft123!"
if "%NEFT_BOOTSTRAP_CLIENT_EMAIL%"=="" set "NEFT_BOOTSTRAP_CLIENT_EMAIL=client@neft.local"
if "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"=="" set "NEFT_BOOTSTRAP_CLIENT_PASSWORD=Client123!"
if "%NEFT_BOOTSTRAP_PARTNER_EMAIL%"=="" set "NEFT_BOOTSTRAP_PARTNER_EMAIL=partner@neft.local"
if "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"=="" set "NEFT_BOOTSTRAP_PARTNER_PASSWORD=Partner123!"
if "%NEFT_BOOTSTRAP_PASSWORD_VERSION%"=="" set "NEFT_BOOTSTRAP_PASSWORD_VERSION=2"
if "%NEFT_DEMO_CLIENT_UUID%"=="" set "NEFT_DEMO_CLIENT_UUID=00000000-0000-0000-0000-000000000001"

echo [INFO] Seeding auth users...
docker compose -f "%COMPOSE_FILE%" exec -T -e NEFT_BOOTSTRAP_PASSWORD_VERSION=%NEFT_BOOTSTRAP_PASSWORD_VERSION% auth-host python -c "import asyncio; from app.bootstrap import bootstrap_required_users; from app.settings import get_settings; asyncio.run(bootstrap_required_users(get_settings()))"
if errorlevel 1 (
  echo [FAIL] auth user seed failed
  exit /b 1
)

echo [INFO] Seeding processing_core demo entities...
docker compose -f "%COMPOSE_FILE%" exec -T core-api python -c "from app.db import get_sessionmaker; from app.services.bootstrap import ensure_demo_client, ensure_demo_partner, ensure_demo_portal_bindings; db=get_sessionmaker()(); ensure_demo_client(db); ensure_demo_partner(db); ensure_demo_portal_bindings(db); db.close()"
if errorlevel 1 (
  echo [FAIL] processing_core seed failed
  exit /b 1
)

echo.
echo [OK] Seed completed
echo   admin   : %NEFT_BOOTSTRAP_ADMIN_EMAIL% / %NEFT_BOOTSTRAP_ADMIN_PASSWORD%
echo   partner : %NEFT_BOOTSTRAP_PARTNER_EMAIL% / %NEFT_BOOTSTRAP_PARTNER_PASSWORD%
echo   client  : %NEFT_BOOTSTRAP_CLIENT_EMAIL% / %NEFT_BOOTSTRAP_CLIENT_PASSWORD%
echo   tenant  : neft
