@echo off
setlocal

set TARGET=%1
if "%TARGET%"=="" set TARGET=postgres

set SCHEMA=%2
if "%SCHEMA%"=="" set SCHEMA=processing_core

echo [simulate] target=%TARGET% schema=%SCHEMA%

docker compose exec -T %TARGET% sh -lc "PGPASSWORD=${POSTGRES_PASSWORD} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -v ON_ERROR_STOP=1 -c \"CREATE SCHEMA IF NOT EXISTS %SCHEMA%; CREATE TABLE IF NOT EXISTS %SCHEMA%.clients (id uuid PRIMARY KEY, name varchar(255)); CREATE TABLE IF NOT EXISTS %SCHEMA%.alembic_version_core (version_num varchar(128) PRIMARY KEY NOT NULL); TRUNCATE TABLE %SCHEMA%.alembic_version_core;\""
if errorlevel 1 exit /b 1

echo [simulate] done: schema has tables, alembic_version_core is empty
endlocal
