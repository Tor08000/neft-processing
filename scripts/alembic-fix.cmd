@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"

echo [alembic-fix] current:
docker compose -f %COMPOSE_FILE% exec -T core-api alembic -c /app/app/alembic.ini current
if errorlevel 1 exit /b 1

echo [alembic-fix] heads:
docker compose -f %COMPOSE_FILE% exec -T core-api alembic -c /app/app/alembic.ini heads
if errorlevel 1 exit /b 1

if "%ALLOW_STAMP%"=="1" (
  echo [alembic-fix] ALLOW_STAMP=1 -> stamping head (dev only)
  docker compose -f %COMPOSE_FILE% exec -T core-api alembic -c /app/app/alembic.ini stamp head
  if errorlevel 1 exit /b 1
) else (
  echo [alembic-fix] stamp skipped; set ALLOW_STAMP=1 to run stamp head
)

endlocal
