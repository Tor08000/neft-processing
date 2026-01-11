@echo off
setlocal

if "%COMPOSE_FILE%"=="" (
  set COMPOSE_FILE=docker-compose.yml
)

docker compose -f "%COMPOSE_FILE%" up -d postgres redis minio minio-health minio-init
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

docker compose -f "%COMPOSE_FILE%" run --rm core-api pytest -q app/tests/system app/tests/smoke app/tests/contracts app/tests/integration -vv -s
exit /b %ERRORLEVEL%
