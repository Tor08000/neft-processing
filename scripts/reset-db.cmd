@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%COMPOSE_FILE%"=="" set "COMPOSE_FILE=docker-compose.yml"

echo [reset-db] stopping stack and dropping volumes...
docker compose -f %COMPOSE_FILE% down -v
if errorlevel 1 exit /b 1

echo [reset-db] starting postgres...
docker compose -f %COMPOSE_FILE% up -d postgres
if errorlevel 1 exit /b 1

echo [reset-db] waiting for postgres to accept connections...
docker compose -f %COMPOSE_FILE% exec -T postgres sh -lc "until pg_isready -U ${POSTGRES_USER:-neft} -d ${POSTGRES_DB:-neft}; do sleep 1; done"
if errorlevel 1 exit /b 1

echo [reset-db] starting core-api with rebuild...
docker compose -f %COMPOSE_FILE% up -d --build core-api
if errorlevel 1 exit /b 1

echo [reset-db] waiting for core-api health...
set /a _wait=0
:wait_health
docker compose -f %COMPOSE_FILE% ps core-api | findstr /I "healthy" >NUL
if not errorlevel 1 goto done_health
set /a _wait+=1
if %_wait% GEQ 60 (
  echo [reset-db] core-api did not become healthy in time
  exit /b 1
)
timeout /t 2 /nobreak >NUL
goto wait_health

:done_health
if "%RUN_SEED%"=="1" (
  echo [reset-db] running seed...
  docker compose -f %COMPOSE_FILE% exec -T core-api python -m app.scripts.seed_demo
)

echo [reset-db] done
endlocal
