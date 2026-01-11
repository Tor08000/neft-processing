@echo off
setlocal

set "CONTAINER=neft-processing-clickhouse-1"
for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "BACKUP_DIR=%ROOT%\backups\clickhouse"

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f "delims=" %%i in ('docker ps -q -f name=%CONTAINER%') do set "CH_ID=%%i"
if "%CH_ID%"=="" (
  echo [backup][WARN] clickhouse container not running, skipping
  exit /b 0
)

set "SNAP="
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "SNAP=ch_%%i"

echo [backup] creating clickhouse snapshot %SNAP%
docker exec %CONTAINER% sh -lc "set -e; SNAP=%SNAP%; tables=$(clickhouse-client --query 'SHOW TABLES'); if [ -z \"$tables\" ]; then echo '[backup][WARN] no tables found'; exit 0; fi; for t in $tables; do clickhouse-client --query \"ALTER TABLE $t FREEZE WITH NAME '$SNAP'\"; done; tar -czf /var/lib/clickhouse/$SNAP.tar.gz -C /var/lib/clickhouse shadow/$SNAP"
if errorlevel 1 (
  echo [backup][ERROR] clickhouse snapshot failed
  exit /b 1
)

docker cp %CONTAINER%:/var/lib/clickhouse/%SNAP%.tar.gz "%BACKUP_DIR%\%SNAP%.tar.gz"
if errorlevel 1 (
  echo [backup][ERROR] clickhouse backup copy failed
  exit /b 1
)

docker exec %CONTAINER% rm -f /var/lib/clickhouse/%SNAP%.tar.gz >NUL 2>NUL

echo [backup] clickhouse backup saved to %BACKUP_DIR%\%SNAP%.tar.gz
exit /b 0
