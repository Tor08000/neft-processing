@echo off
setlocal
set "DC_CMD=%DOCKER_COMPOSE%"
if "%DC_CMD%"=="" set "DC_CMD=docker compose"

set "DB_NAME=%POSTGRES_DB%"
if "%DB_NAME%"=="" set "DB_NAME=neft"
set "DB_USER=%POSTGRES_USER%"
if "%DB_USER%"=="" set "DB_USER=neft"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "TS=%%i"
for %%i in ("%~dp0..\..") do set "ROOT=%%~fi"
set "BACKUP_DIR=%ROOT%\backups\postgres"
set "BACKUP_FILE=%BACKUP_DIR%\pg_%TS%.backup"

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [backup] postgres dump to %BACKUP_FILE%
%DC_CMD% exec -T postgres pg_dump -Fc -U %DB_USER% -d %DB_NAME% > "%BACKUP_FILE%"
if errorlevel 1 (
  echo [backup][ERROR] pg_dump failed
  exit /b 1
)

echo [backup] postgres backup complete

echo [backup] optional upload to MinIO (backups/postgres/)
set "MINIO_ENDPOINT=%MINIO_ENDPOINT%"
if "%MINIO_ENDPOINT%"=="" set "MINIO_ENDPOINT=http://localhost:9000"
set "MINIO_ACCESS_KEY=%NEFT_S3_ACCESS_KEY%"
if "%MINIO_ACCESS_KEY%"=="" set "MINIO_ACCESS_KEY=%MINIO_ROOT_USER%"
set "MINIO_SECRET_KEY=%NEFT_S3_SECRET_KEY%"
if "%MINIO_SECRET_KEY%"=="" set "MINIO_SECRET_KEY=%MINIO_ROOT_PASSWORD%"

where mc >NUL 2>NUL
if %errorlevel%==0 (
  mc alias set local %MINIO_ENDPOINT% %MINIO_ACCESS_KEY% %MINIO_SECRET_KEY% >NUL
  mc cp "%BACKUP_FILE%" local/backups/postgres/
  if errorlevel 1 (
    echo [backup][WARN] MinIO upload failed
  ) else (
    echo [backup] MinIO upload complete
  )
) else (
  echo [backup][WARN] mc not found, skipping MinIO upload
)

exit /b 0
