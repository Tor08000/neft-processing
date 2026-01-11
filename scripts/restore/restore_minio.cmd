@echo off
setlocal

for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "BACKUP_DIR=%ROOT%\backups\minio"

set "MINIO_ENDPOINT=%MINIO_ENDPOINT%"
if "%MINIO_ENDPOINT%"=="" set "MINIO_ENDPOINT=http://localhost:9000"
set "MINIO_ACCESS_KEY=%NEFT_S3_ACCESS_KEY%"
if "%MINIO_ACCESS_KEY%"=="" set "MINIO_ACCESS_KEY=%MINIO_ROOT_USER%"
set "MINIO_SECRET_KEY=%NEFT_S3_SECRET_KEY%"
if "%MINIO_SECRET_KEY%"=="" set "MINIO_SECRET_KEY=%MINIO_ROOT_PASSWORD%"

where mc >NUL 2>NUL
if not %errorlevel%==0 (
  echo [restore][ERROR] mc (MinIO client) not found in PATH
  exit /b 1
)

mc alias set local %MINIO_ENDPOINT% %MINIO_ACCESS_KEY% %MINIO_SECRET_KEY% >NUL

for %%b in (docs exports artifacts) do (
  if not exist "%BACKUP_DIR%\%%b" (
    echo [restore][WARN] backup for bucket %%b not found, skipping
  ) else (
    echo [restore] restoring bucket %%b
    mc mirror --overwrite "%BACKUP_DIR%\%%b" local/%%b
    if errorlevel 1 (
      echo [restore][ERROR] bucket %%b restore failed
      exit /b 1
    )
  )
)

echo [restore] minio restore complete
exit /b 0
