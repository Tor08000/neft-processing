@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%1"=="" (
  set TARGET=core-api
) else (
  set TARGET=%1
)

set SCHEMA=processing_core

call :run_cmd "1) Schema/search_path diagnostics" docker compose exec -T %TARGET% sh -lc "psql \"${DATABASE_URL}\" -v ON_ERROR_STOP=1 -Atc \"select current_schema(), current_setting('search_path')\""
if errorlevel 1 exit /b 1

call :run_cmd "2) Alembic version table presence" docker compose exec -T %TARGET% sh -lc "psql \"${DATABASE_URL}\" -v ON_ERROR_STOP=1 -Atc \"select to_regclass('%SCHEMA%.alembic_version_core')\""
if errorlevel 1 exit /b 1

call :run_cmd "3) Ensure schema + version table" docker compose exec -T %TARGET% sh -lc "psql \"${DATABASE_URL}\" -v ON_ERROR_STOP=1 -c \"DO $$ BEGIN CREATE SCHEMA IF NOT EXISTS %SCHEMA%; IF to_regclass('%SCHEMA%.alembic_version_core') IS NULL THEN CREATE TABLE %SCHEMA%.alembic_version_core (version_num varchar(128) NOT NULL); END IF; END $$;\""
if errorlevel 1 exit /b 1

call :run_cmd "4) Alembic tables in public" docker compose exec -T %TARGET% sh -lc "psql \"${DATABASE_URL}\" -v ON_ERROR_STOP=1 -Atc \"select n.nspname || '.' || c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relname like 'alembic_version%' order by 1\""
if errorlevel 1 exit /b 1

call :try_cmd "5) Alembic current" docker compose exec -T %TARGET% sh -lc "alembic -c app/alembic.ini current"
call :try_cmd "6) Alembic heads" docker compose exec -T %TARGET% sh -lc "alembic -c app/alembic.ini heads"

echo [repair-processing-core] completed
exit /b 0

:run_cmd
set step=%~1
shift
set command=%*
echo [repair-processing-core] %step%
%command%
if errorlevel 1 (
  echo [repair-processing-core] FAILED: %step%
  exit /b 1
)
exit /b 0

:try_cmd
set step=%~1
shift
set command=%*
echo [repair-processing-core] %step%
%command%
if errorlevel 1 (
  echo [repair-processing-core] warning: %step% failed
)
exit /b 0
