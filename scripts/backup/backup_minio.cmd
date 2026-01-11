@echo off
setlocal

for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "BACKUP_DIR=%ROOT%\backups\minio"

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set "MINIO_ENDPOINT=%MINIO_ENDPOINT%"
if "%MINIO_ENDPOINT%"=="" set "MINIO_ENDPOINT=http://localhost:9000"
set "MINIO_ACCESS_KEY=%NEFT_S3_ACCESS_KEY%"
if "%MINIO_ACCESS_KEY%"=="" set "MINIO_ACCESS_KEY=%MINIO_ROOT_USER%"
set "MINIO_SECRET_KEY=%NEFT_S3_SECRET_KEY%"
if "%MINIO_SECRET_KEY%"=="" set "MINIO_SECRET_KEY=%MINIO_ROOT_PASSWORD%"

where mc >NUL 2>NUL
if not %errorlevel%==0 (
  echo [backup][ERROR] mc (MinIO client) not found in PATH
  exit /b 1
)

mc alias set local %MINIO_ENDPOINT% %MINIO_ACCESS_KEY% %MINIO_SECRET_KEY% >NUL

for %%b in (docs exports artifacts) do (
  echo [backup] mirroring bucket %%b
  mc mirror --overwrite local/%%b "%BACKUP_DIR%\%%b"
  if errorlevel 1 (
    echo [backup][ERROR] bucket %%b backup failed
    exit /b 1
  )
)

echo [backup] minio backup complete at %BACKUP_DIR%
exit /b 0
