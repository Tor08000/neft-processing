@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "BASE_URL=%BASE_URL%"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

if not "%EDO_E2E_ENABLED%"=="1" (
  echo [SKIP] EDO SBIS revoke smoke is disabled. Set EDO_E2E_ENABLED=1 and SBIS credentials to run external EDO.
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
  echo [FAIL] DOCUMENT_ID is required for EDO SBIS revoke smoke.
  exit /b 1
)

set "STATUS="
for /f "usebackq tokens=*" %%c in (`curl -sS -o edo_revoke.json -w "%%{http_code}" -X POST "%BASE_URL%/api/core/v1/admin/edo/documents/%DOCUMENT_ID%/revoke" -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" 2^>nul`) do set "STATUS=%%c"

if not "%STATUS:~0,1%"=="2" (
  echo [FAIL] EDO SBIS revoke returned HTTP %STATUS%.
  type edo_revoke.json
  exit /b 1
)

python -c "import json, sys; data=json.load(open('edo_revoke.json', encoding='utf-8')); sys.exit(0 if data.get('id') and data.get('status') else 1)"
if errorlevel 1 (
  echo [FAIL] EDO SBIS revoke response has unexpected shape.
  type edo_revoke.json
  exit /b 1
)

type edo_revoke.json
echo PASS
