@echo off
setlocal
set "DC_CMD=%DOCKER_COMPOSE%"
if "%DC_CMD%"=="" set "DC_CMD=docker compose"

set "DB_NAME=%POSTGRES_DB%"
if "%DB_NAME%"=="" set "DB_NAME=neft"
set "DB_USER=%POSTGRES_USER%"
if "%DB_USER%"=="" set "DB_USER=neft"

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
  echo [restore][ERROR] no postgres backup found in %BACKUP_DIR%
  exit /b 1
)

if not exist "%BACKUP_FILE%" (
  echo [restore][ERROR] backup file not found: %BACKUP_FILE%
  exit /b 1
)

echo [restore] restoring postgres from %BACKUP_FILE%
type "%BACKUP_FILE%" | %DC_CMD% exec -T postgres pg_restore -U %DB_USER% -d %DB_NAME% --clean --if-exists -
if errorlevel 1 (
  echo [restore][ERROR] pg_restore failed
  exit /b 1
)

echo [restore] postgres restore complete
exit /b 0
