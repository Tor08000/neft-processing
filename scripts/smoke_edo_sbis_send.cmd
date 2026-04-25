@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "BASE_URL=%BASE_URL%"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost"

if not "%EDO_E2E_ENABLED%"=="1" (
  echo [SKIP] EDO SBIS send smoke is disabled. Set EDO_E2E_ENABLED=1 and SBIS credentials to run external EDO.
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

call :require DOC_ID || exit /b 1
call :require SUBJECT_TYPE || exit /b 1
call :require SUBJECT_ID || exit /b 1
call :require COUNTERPARTY_ID || exit /b 1
call :require ACCOUNT_ID || exit /b 1
call :require DOC_KIND || exit /b 1

set "DEDUPE_KEY=%DEDUPE_KEY%"
if "%DEDUPE_KEY%"=="" set "DEDUPE_KEY=sbis-send-%DOC_ID%"

set "REQUEST_FILE=%TEMP%\edo_sbis_send_request_%RANDOM%.json"
set "STATUS="
python -c "import json; from pathlib import Path; Path(r'%REQUEST_FILE%').write_text(json.dumps({'document_registry_id': r'%DOC_ID%', 'subject_type': r'%SUBJECT_TYPE%', 'subject_id': r'%SUBJECT_ID%', 'counterparty_id': r'%COUNTERPARTY_ID%', 'document_kind': r'%DOC_KIND%', 'account_id': r'%ACCOUNT_ID%', 'dedupe_key': r'%DEDUPE_KEY%'}), encoding='utf-8')"

for /f "usebackq tokens=*" %%c in (`curl -sS -o edo_send_response.json -w "%%{http_code}" -X POST "%BASE_URL%/api/core/v1/admin/edo/documents/send" -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" --data-binary "@%REQUEST_FILE%" 2^>nul`) do set "STATUS=%%c"

del /q "%REQUEST_FILE%" 2>nul

if not "%STATUS:~0,1%"=="2" (
  echo [FAIL] EDO SBIS send returned HTTP %STATUS%.
  type edo_send_response.json
  exit /b 1
)

python -c "import json, sys; data=json.load(open('edo_send_response.json', encoding='utf-8')); sys.exit(0 if data.get('document') and data.get('status') else 1)"
if errorlevel 1 (
  echo [FAIL] EDO SBIS send response has unexpected shape.
  type edo_send_response.json
  exit /b 1
)

type edo_send_response.json
echo PASS
exit /b 0

:require
set "_required_value="
call set "_required_value=%%%~1%%"
if "%_required_value%"=="" (
  echo [FAIL] %~1 is required for EDO SBIS send smoke.
  exit /b 1
)
exit /b 0
