@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%NEFT_BOOTSTRAP_PARTNER_EMAIL%"=="" (
  set "PARTNER_EMAIL=partner@neft.local"
) else (
  set "PARTNER_EMAIL=%NEFT_BOOTSTRAP_PARTNER_EMAIL%"
)
if "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"=="" (
  set "PARTNER_PASSWORD=Partner123!"
) else (
  set "PARTNER_PASSWORD=%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"
)

set "LOGIN_FILE=%TEMP%\partner_bootstrap_login_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\partner_bootstrap_status_%RANDOM%.txt"

curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%PARTNER_EMAIL%\",\"password\":\"%PARTNER_PASSWORD%\",\"portal\":\"partner\"}" "%GATEWAY_BASE%%AUTH_BASE%/login" > "%STATUS_FILE%"
set /p LOGIN_STATUS=<"%STATUS_FILE%"
if not "%LOGIN_STATUS%"=="200" (
  echo [FAIL] partner login HTTP %LOGIN_STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%T"
if "%PARTNER_TOKEN%"=="" (
  echo [FAIL] partner login missing access_token
  exit /b 1
)

call :check_json "partner auth/me" "%GATEWAY_BASE%%AUTH_BASE%/me" "-H \"Authorization: Bearer %PARTNER_TOKEN%\" -H \"X-Portal: partner\"" || exit /b 1
call :check_json "partner core portal/me" "%GATEWAY_BASE%%CORE_BASE%/portal/me" "-H \"Authorization: Bearer %PARTNER_TOKEN%\"" || exit /b 1

echo [PASS] partner bootstrap OK
exit /b 0

:check_json
set "LABEL=%~1"
set "URL=%~2"
set "HEADERS=%~3"
set "RESP_FILE=%TEMP%\partner_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\partner_bootstrap_resp_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" %HEADERS% "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  type "%RESP_FILE%"
  exit /b 1
)
python -c "import json; from pathlib import Path; json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore'))" >NUL 2>&1
if errorlevel 1 (
  echo [FAIL] %LABEL% invalid JSON
  type "%RESP_FILE%"
  exit /b 1
)

echo [PASS] %LABEL%
exit /b 0
