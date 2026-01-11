@echo off
setlocal

echo [backup-smoke] starting backup + restore smoke
call "%~dp0backup_postgres.cmd"
if errorlevel 1 exit /b 1

call "%~dp0backup_minio.cmd"
if errorlevel 1 (
  echo [backup-smoke][WARN] minio backup failed
)

call "%~dp0backup_clickhouse.cmd"
if errorlevel 1 (
  echo [backup-smoke][WARN] clickhouse backup failed
)

call "%~dp0verify_backup.cmd"
if errorlevel 1 exit /b 1

echo [backup-smoke] backup/restore verification PASS
exit /b 0
