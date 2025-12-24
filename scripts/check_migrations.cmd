@echo off
setlocal enabledelayedexpansion

echo [check-migrations] starting postgres...
docker compose up -d postgres
if errorlevel 1 exit /b %errorlevel%

echo [check-migrations] checking alembic heads...
for /f %%c in ('docker compose run --rm --entrypoint "" core-api alembic -c app/alembic.ini heads ^| find /c /v ""') do (
  set "HEADS_COUNT=%%c"
)

if "%HEADS_COUNT%"=="" (
  echo [check-migrations] failed to read alembic heads
  exit /b 1
)

if not "%HEADS_COUNT%"=="1" (
  echo [check-migrations] expected 1 alembic head, got %HEADS_COUNT%
  echo [check-migrations] resolve with: alembic merge ^<head1^> ^<head2^>
  exit /b 1
)

echo [check-migrations] running alembic upgrade head...
docker compose run --rm --entrypoint "" core-api alembic -c app/alembic.ini upgrade head
if errorlevel 1 exit /b %errorlevel%

echo [check-migrations] success
endlocal
