@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "BASE_URL=%BASE_URL%"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

if not "%EDO_E2E_ENABLED%"=="1" (
  echo [SKIP] EDO SBIS status smoke is disabled. Set EDO_E2E_ENABLED=1 and SBIS credentials to run external EDO.
  exit /b 0
)

if /I not "%EDO_PROVIDER%"=="SBIS" (
  echo [FAIL] EDO_PROVIDER must be SBIS when EDO_E2E_ENABLED=1.
  exit /b 1
)

set "ADMIN_TOKEN=%ADMIN_TOKEN%"
if "%ADMIN_TOKEN%"=="" (
  for /f "usebackq delims=" %%T in (`scripts\get_admin_token.cmd 2^>nul`) do set "ADMIN_TOKEN=%%T"
)
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] ADMIN_TOKEN is required and scripts\get_admin_token.cmd did not return a token.
  exit /b 1
)

set "DOCUMENT_ID=%DOCUMENT_ID%"
if "%DOCUMENT_ID%"=="" (
  echo [FAIL] DOCUMENT_ID is required for EDO SBIS status smoke.
  exit /b 1
)

set "MAX_ATTEMPTS=%MAX_ATTEMPTS%"
if "%MAX_ATTEMPTS%"=="" set "MAX_ATTEMPTS=20"
set "SLEEP_SECONDS=%SLEEP_SECONDS%"
if "%SLEEP_SECONDS%"=="" set "SLEEP_SECONDS=15"

for /L %%i in (1,1,%MAX_ATTEMPTS%) do (
  set "STATUS="
  for /f "usebackq tokens=*" %%c in (`curl -sS -o edo_status.json -w "%%{http_code}" -X POST "%BASE_URL%/api/core/v1/admin/edo/documents/%DOCUMENT_ID%/refresh-status" -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" 2^>nul`) do set "STATUS=%%c"
  if not "!STATUS:~0,1!"=="2" (
    echo [FAIL] EDO SBIS status returned HTTP !STATUS!.
    type edo_status.json
    exit /b 1
  )
  findstr /I "\"SIGNED\"" edo_status.json >nul
  if !errorlevel! EQU 0 (
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
