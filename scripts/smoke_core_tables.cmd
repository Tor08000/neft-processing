@echo off
setlocal enabledelayedexpansion

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"

set "CORE_HEALTH_URL=%BASE_URL%/api/core/health"
set "CLIENT_USERS_URL=%BASE_URL%/api/core/client/users"
set "CLIENT_CARDS_URL=%BASE_URL%/api/core/client/cards"

echo [smoke_core_tables] Resetting containers and volumes...
docker compose -f "%COMPOSE_FILE%" down -v
if errorlevel 1 exit /b 1

echo [smoke_core_tables] Starting stack...
docker compose -f "%COMPOSE_FILE%" up -d --build
if errorlevel 1 exit /b 1

echo [smoke_core_tables] Waiting for core-api health endpoint: %CORE_HEALTH_URL%
set /a ATTEMPT=0
:wait_core
set /a ATTEMPT+=1
curl -sS -o "%TEMP%\core_health_smoke.json" -w "%%{http_code}" "%CORE_HEALTH_URL%" > "%TEMP%\core_health_smoke.status"
set /p CORE_STATUS=<"%TEMP%\core_health_smoke.status"
if "%CORE_STATUS%"=="200" goto core_ready
if %ATTEMPT% GEQ 60 (
  echo [smoke_core_tables] core-api health check failed after %ATTEMPT% attempts. 1>&2
  type "%TEMP%\core_health_smoke.json" 1>&2
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_core

:core_ready
echo [smoke_core_tables] core-api is healthy.

echo [smoke_core_tables] Verifying required DB tables in processing_core schema...
docker compose -f "%COMPOSE_FILE%" exec -T postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -c "select table_name from information_schema.tables where table_schema='processing_core' and table_name in ('users','clients','cards','client_user_roles','card_limits') order by table_name;" > "%TEMP%\core_tables_psql.txt"
if errorlevel 1 exit /b 1

type "%TEMP%\core_tables_psql.txt"
findstr /C:"client_user_roles" "%TEMP%\core_tables_psql.txt" >nul || (echo [smoke_core_tables] missing table client_user_roles 1>&2 & exit /b 1)
findstr /C:"card_limits" "%TEMP%\core_tables_psql.txt" >nul || (echo [smoke_core_tables] missing table card_limits 1>&2 & exit /b 1)

if "%CLIENT_TOKEN%"=="" (
  echo [smoke_core_tables] CLIENT_TOKEN is not set. Endpoint checks are skipped; DB verification passed.
  exit /b 0
)

echo [smoke_core_tables] Checking /api/core/client/users (expect 200)...
curl -sS -o "%TEMP%\client_users_smoke.json" -w "%%{http_code}" "%CLIENT_USERS_URL%" -H "Authorization: Bearer %CLIENT_TOKEN%" > "%TEMP%\client_users_smoke.status"
set /p USERS_STATUS=<"%TEMP%\client_users_smoke.status"
if not "%USERS_STATUS%"=="200" (
  echo [smoke_core_tables] /client/users returned %USERS_STATUS% 1>&2
  type "%TEMP%\client_users_smoke.json" 1>&2
  exit /b 1
)

echo [smoke_core_tables] Checking /api/core/client/cards (expect 200)...
curl -sS -o "%TEMP%\client_cards_smoke.json" -w "%%{http_code}" "%CLIENT_CARDS_URL%" -H "Authorization: Bearer %CLIENT_TOKEN%" > "%TEMP%\client_cards_smoke.status"
set /p CARDS_STATUS=<"%TEMP%\client_cards_smoke.status"
if not "%CARDS_STATUS%"=="200" (
  echo [smoke_core_tables] /client/cards returned %CARDS_STATUS% 1>&2
  type "%TEMP%\client_cards_smoke.json" 1>&2
  exit /b 1
)

echo [smoke_core_tables] SUCCESS: tables exist and client endpoints returned 200.
exit /b 0
