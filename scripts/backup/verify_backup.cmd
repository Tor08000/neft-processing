@echo off
setlocal

set "DB_NAME=%POSTGRES_DB%"
if "%DB_NAME%"=="" set "DB_NAME=neft"
set "DB_USER=%POSTGRES_USER%"
if "%DB_USER%"=="" set "DB_USER=neft"
set "DB_PASSWORD=%POSTGRES_PASSWORD%"
if "%DB_PASSWORD%"=="" set "DB_PASSWORD=neft"

for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "BACKUP_DIR=%ROOT%\backups\postgres"

set "BACKUP_FILE=%~1"
if "%BACKUP_FILE%"=="" (
  for /f "delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\pg_*.backup"') do (
    set "BACKUP_FILE=%BACKUP_DIR%\%%f"
    goto :found
  )
)
:found

if "%BACKUP_FILE%"=="" (
  echo [verify][ERROR] no postgres backup found in %BACKUP_DIR%
  exit /b 1
)

if not exist "%BACKUP_FILE%" (
  echo [verify][ERROR] backup file not found: %BACKUP_FILE%
  exit /b 1
)

echo [verify] starting temporary postgres container
set "VERIFY_CONTAINER=neft-pg-verify"
docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL

docker run -d --name %VERIFY_CONTAINER% -e POSTGRES_DB=%DB_NAME% -e POSTGRES_USER=%DB_USER% -e POSTGRES_PASSWORD=%DB_PASSWORD% -p 55432:5432 -v "%BACKUP_DIR%:/backups" postgres:16 >NUL
if errorlevel 1 (
  echo [verify][ERROR] failed to start verification postgres
  exit /b 1
)

set /a READY=0
for /l %%i in (1,1,20) do (
  docker exec %VERIFY_CONTAINER% pg_isready -U %DB_USER% -d %DB_NAME% >NUL 2>NUL
  if not errorlevel 1 (
    set /a READY=1
    goto :ready
  )
  timeout /t 2 /nobreak >NUL
)
:ready

if %READY%==0 (
  echo [verify][ERROR] postgres did not become ready
  docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL
  exit /b 1
)

echo [verify] restoring backup into temporary postgres
set "BACKUP_BASENAME=%~nx1"
if "%BACKUP_BASENAME%"=="" for %%f in ("%BACKUP_FILE%") do set "BACKUP_BASENAME=%%~nxf"

type "%BACKUP_FILE%" | docker exec -i %VERIFY_CONTAINER% pg_restore -U %DB_USER% -d %DB_NAME% --clean --if-exists -
if errorlevel 1 (
  echo [verify][ERROR] pg_restore failed
  docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL
  exit /b 1
)

echo [verify] checking schema and key tables
for /f "delims=" %%c in ('docker exec %VERIFY_CONTAINER% psql -U %DB_USER% -d %DB_NAME% -t -c "select count(*) from information_schema.tables where table_schema='public';"') do set "TABLE_COUNT=%%c"
for /f "delims=" %%c in ('docker exec %VERIFY_CONTAINER% psql -U %DB_USER% -d %DB_NAME% -t -c "select count(*) from alembic_version;"') do set "ALEMBIC_COUNT=%%c"
for /f "delims=" %%c in ('docker exec %VERIFY_CONTAINER% psql -U %DB_USER% -d %DB_NAME% -t -c "select count(*) from information_schema.tables where table_schema='public' and table_name in ('accounts','users');"') do set "KEY_TABLES=%%c"

if "%TABLE_COUNT%"=="" set "TABLE_COUNT=0"
if "%ALEMBIC_COUNT%"=="" set "ALEMBIC_COUNT=0"
if "%KEY_TABLES%"=="" set "KEY_TABLES=0"

if %TABLE_COUNT% LEQ 0 (
  echo [verify][ERROR] no tables restored
  docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL
  exit /b 1
)

if %ALEMBIC_COUNT% LEQ 0 (
  echo [verify][ERROR] alembic_version missing
  docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL
  exit /b 1
)

if %KEY_TABLES% LEQ 0 (
  echo [verify][ERROR] key tables missing (accounts/users)
  docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL
  exit /b 1
)

echo [verify] backup verification PASS

docker rm -f %VERIFY_CONTAINER% >NUL 2>NUL
exit /b 0
