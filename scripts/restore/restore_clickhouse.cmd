@echo off
setlocal

set "CONTAINER=neft-processing-clickhouse-1"
for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "BACKUP_DIR=%ROOT%\backups\clickhouse"

set "BACKUP_FILE=%~1"
if "%BACKUP_FILE%"=="" (
  for /f "delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\ch_*.tar.gz"') do (
    set "BACKUP_FILE=%BACKUP_DIR%\%%f"
    goto :found
  )
)
:found

if "%BACKUP_FILE%"=="" (
  echo [restore][WARN] no clickhouse backup found in %BACKUP_DIR%
  exit /b 0
)

for /f "delims=" %%i in ('docker ps -q -f name=%CONTAINER%') do set "CH_ID=%%i"
if "%CH_ID%"=="" (
  echo [restore][WARN] clickhouse container not running, skipping
  exit /b 0
)

echo [restore] clickhouse restore requires clickhouse-backup or manual attach of frozen parts.
echo [restore] backup file located at %BACKUP_FILE%
echo [restore] if clickhouse-backup is installed, run inside container:
echo [restore]   clickhouse-backup restore --backup-name <name>

exit /b 0
