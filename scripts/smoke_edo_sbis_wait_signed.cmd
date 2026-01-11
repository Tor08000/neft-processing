@echo off
setlocal enabledelayedexpansion

set BASE_URL=%BASE_URL%
if "%BASE_URL%"=="" set BASE_URL=http://localhost:8080

set ADMIN_TOKEN=%ADMIN_TOKEN%
if "%ADMIN_TOKEN%"=="" (
  echo ADMIN_TOKEN is required
  exit /b 1
)

set DOCUMENT_ID=%DOCUMENT_ID%
if "%DOCUMENT_ID%"=="" (
  echo DOCUMENT_ID is required
  exit /b 1
)

set MAX_ATTEMPTS=20
set SLEEP_SECONDS=15

for /L %%i in (1,1,%MAX_ATTEMPTS%) do (
  curl -s -X POST "%BASE_URL%/api/core/v1/admin/edo/documents/%DOCUMENT_ID%/refresh-status" ^
    -H "Authorization: Bearer %ADMIN_TOKEN%" ^
    -H "Content-Type: application/json" > edo_status.json
  findstr /I "SIGNED" edo_status.json >nul
  if %errorlevel%==0 (
    echo SIGNED
    type edo_status.json
    echo PASS
    exit /b 0
  )
  timeout /t %SLEEP_SECONDS% /nobreak >nul
)

type edo_status.json
echo FAIL
exit /b 1
