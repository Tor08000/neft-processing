@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "OVERALL_FAIL=0"
set "FAIL_CONTEXT="
set "FAIL_FILE="

call :login_portal "client" "%NEFT_BOOTSTRAP_CLIENT_EMAIL%" "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%" "client@neft.local" "client"
if not "%LAST_RC%"=="0" goto end
call :login_portal "partner" "%NEFT_BOOTSTRAP_PARTNER_EMAIL%" "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%" "partner@neft.local" "partner"
if not "%LAST_RC%"=="0" goto end
call :login_portal "admin" "%NEFT_BOOTSTRAP_ADMIN_EMAIL%" "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%" "admin@neft.local" "admin"
if not "%LAST_RC%"=="0" goto end

call :verify "client verify (client token)" "%GATEWAY_BASE%%CORE_BASE%/client/auth/verify" "%CLIENT_TOKEN%" "204"
if not "%LAST_RC%"=="0" goto end
call :verify "client verify (partner token)" "%GATEWAY_BASE%%CORE_BASE%/client/auth/verify" "%PARTNER_TOKEN%" "401"
if not "%LAST_RC%"=="0" goto end
call :verify "client verify (admin token)" "%GATEWAY_BASE%%CORE_BASE%/client/auth/verify" "%ADMIN_TOKEN%" "401"
if not "%LAST_RC%"=="0" goto end

call :verify "partner verify (partner token)" "%GATEWAY_BASE%%CORE_BASE%/partner/auth/verify" "%PARTNER_TOKEN%" "204"
if not "%LAST_RC%"=="0" goto end
call :verify "partner verify (client token)" "%GATEWAY_BASE%%CORE_BASE%/partner/auth/verify" "%CLIENT_TOKEN%" "401"
if not "%LAST_RC%"=="0" goto end
call :verify "partner verify (admin token)" "%GATEWAY_BASE%%CORE_BASE%/partner/auth/verify" "%ADMIN_TOKEN%" "401"
if not "%LAST_RC%"=="0" goto end

call :verify "admin verify (admin token)" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%ADMIN_TOKEN%" "204"
if not "%LAST_RC%"=="0" goto end
call :verify "admin verify (client token)" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%CLIENT_TOKEN%" "401"
if not "%LAST_RC%"=="0" goto end
call :verify "admin verify (partner token)" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%PARTNER_TOKEN%" "401"
if not "%LAST_RC%"=="0" goto end

goto end

:login_portal
set "LAST_RC=0"
set "LABEL=%~1"
set "ENV_EMAIL=%~2"
set "ENV_PASSWORD=%~3"
set "DEFAULT_EMAIL=%~4"
set "DEFAULT_PASSWORD=%~5"

if "%ENV_EMAIL%"=="" (
  set "PORTAL_EMAIL=%DEFAULT_EMAIL%"
) else (
  set "PORTAL_EMAIL=%ENV_EMAIL%"
)
if "%ENV_PASSWORD%"=="" (
  set "PORTAL_PASSWORD=%DEFAULT_PASSWORD%"
) else (
  set "PORTAL_PASSWORD=%ENV_PASSWORD%"
)

set "LOGIN_FILE=%TEMP%\slice0_%LABEL%_login_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\slice0_%LABEL%_status_%RANDOM%.txt"

curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%PORTAL_EMAIL%\",\"password\":\"%PORTAL_PASSWORD%\",\"portal\":\"%LABEL%\"}" "%GATEWAY_BASE%%AUTH_BASE%/login" > "%STATUS_FILE%"
set /p LOGIN_STATUS=<"%STATUS_FILE%"
if not "%LOGIN_STATUS%"=="200" (
  set "OVERALL_FAIL=1"
  set "FAIL_CONTEXT=%LABEL% login HTTP %LOGIN_STATUS%"
  set "FAIL_FILE=%LOGIN_FILE%"
  set "LAST_RC=1"
  goto :eof
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN_VALUE=%%T"
if "%TOKEN_VALUE%"=="" (
  set "OVERALL_FAIL=1"
  set "FAIL_CONTEXT=%LABEL% login missing access_token"
  set "FAIL_FILE=%LOGIN_FILE%"
  set "LAST_RC=1"
  goto :eof
)

if "%LABEL%"=="client" set "CLIENT_TOKEN=%TOKEN_VALUE%"
if "%LABEL%"=="partner" set "PARTNER_TOKEN=%TOKEN_VALUE%"
if "%LABEL%"=="admin" set "ADMIN_TOKEN=%TOKEN_VALUE%"
echo [PASS] %LABEL% login OK
goto :eof

:verify
set "LAST_RC=0"
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "EXPECTED=%~4"

set "RESP_FILE=%TEMP%\slice0_resp_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\slice0_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%URL%" > "%STATUS_FILE%"
set /p RESP_STATUS=<"%STATUS_FILE%"

if "%EXPECTED%"=="204" (
  call :assert_204 "%LABEL%" "%RESP_STATUS%" "%RESP_FILE%"
) else (
  call :assert_401_wrong_portal "%LABEL%" "%RESP_STATUS%" "%RESP_FILE%"
)
if not "%LAST_RC%"=="0" goto :eof

echo [PASS] %LABEL%
goto :eof

:assert_204
set "LAST_RC=0"
set "LABEL=%~1"
set "RESP_STATUS=%~2"
set "RESP_FILE=%~3"

if not "%RESP_STATUS%"=="204" (
  set "OVERALL_FAIL=1"
  set "FAIL_CONTEXT=%LABEL% HTTP %RESP_STATUS% expected 204"
  set "FAIL_FILE=%RESP_FILE%"
  set "LAST_RC=1"
)
goto :eof

:assert_401_wrong_portal
set "LAST_RC=0"
set "LABEL=%~1"
set "RESP_STATUS=%~2"
set "RESP_FILE=%~3"

if not "%RESP_STATUS%"=="401" (
  set "OVERALL_FAIL=1"
  set "FAIL_CONTEXT=%LABEL% HTTP %RESP_STATUS% expected 401"
  set "FAIL_FILE=%RESP_FILE%"
  set "LAST_RC=1"
  goto :eof
)

for /f "usebackq delims=" %%R in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); detail=data.get('detail') or {}; err=data.get('error') or {}; reason=detail.get('reason_code') or err.get('reason_code') or data.get('reason_code') or ''; error_id=detail.get('error_id') or err.get('error_id') or data.get('error_id') or ''; print(f'{reason}|||{error_id}')"`) do set "REASON_AND_ID=%%R"
set "ACTUAL_REASON="
set "ACTUAL_ERROR_ID="
for /f "tokens=1,2 delims=|" %%A in ("%REASON_AND_ID%") do (
  set "ACTUAL_REASON=%%A"
  set "ACTUAL_ERROR_ID=%%B"
)

if /i not "%ACTUAL_REASON%"=="TOKEN_WRONG_PORTAL" (
  set "OVERALL_FAIL=1"
  set "FAIL_CONTEXT=%LABEL% reason_code %ACTUAL_REASON% expected TOKEN_WRONG_PORTAL"
  set "FAIL_FILE=%RESP_FILE%"
  set "LAST_RC=1"
  goto :eof
)

if "%ACTUAL_ERROR_ID%"=="" (
  set "OVERALL_FAIL=1"
  set "FAIL_CONTEXT=%LABEL% missing error_id"
  set "FAIL_FILE=%RESP_FILE%"
  set "LAST_RC=1"
)
goto :eof

:end
if "%OVERALL_FAIL%"=="1" (
  echo [FAIL] %FAIL_CONTEXT%
  if not "%FAIL_FILE%"=="" type "%FAIL_FILE%"
  exit /b 1
)

echo ALL PASS
exit /b 0
