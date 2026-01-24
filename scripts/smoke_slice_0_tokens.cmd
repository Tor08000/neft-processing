@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

call :login_portal "client" "%NEFT_BOOTSTRAP_CLIENT_EMAIL%" "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%" "client@neft.local" "client" || exit /b 1
call :login_portal "partner" "%NEFT_BOOTSTRAP_PARTNER_EMAIL%" "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%" "partner@neft.local" "partner" || exit /b 1
call :login_portal "admin" "%NEFT_BOOTSTRAP_ADMIN_EMAIL%" "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%" "admin@neft.local" "admin" || exit /b 1

call :expect_status "client verify (client token)" "%GATEWAY_BASE%%CORE_BASE%/client/auth/verify" "%CLIENT_TOKEN%" "204" "" || exit /b 1
call :expect_status "client verify (partner token)" "%GATEWAY_BASE%%CORE_BASE%/client/auth/verify" "%PARTNER_TOKEN%" "401" "TOKEN_WRONG_PORTAL" || exit /b 1
call :expect_status "client verify (admin token)" "%GATEWAY_BASE%%CORE_BASE%/client/auth/verify" "%ADMIN_TOKEN%" "401" "TOKEN_WRONG_PORTAL" || exit /b 1

call :expect_status "partner verify (partner token)" "%GATEWAY_BASE%%CORE_BASE%/partner/auth/verify" "%PARTNER_TOKEN%" "204" "" || exit /b 1
call :expect_status "partner verify (client token)" "%GATEWAY_BASE%%CORE_BASE%/partner/auth/verify" "%CLIENT_TOKEN%" "401" "TOKEN_WRONG_PORTAL" || exit /b 1
call :expect_status "partner verify (admin token)" "%GATEWAY_BASE%%CORE_BASE%/partner/auth/verify" "%ADMIN_TOKEN%" "401" "TOKEN_WRONG_PORTAL" || exit /b 1

call :expect_status "admin verify (admin token)" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%ADMIN_TOKEN%" "204" "" || exit /b 1
call :expect_status "admin verify (client token)" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%CLIENT_TOKEN%" "401" "TOKEN_WRONG_PORTAL" || exit /b 1
call :expect_status "admin verify (partner token)" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%PARTNER_TOKEN%" "401" "TOKEN_WRONG_PORTAL" || exit /b 1

echo [PASS] slice 0 token routing hygiene
exit /b 0

:login_portal
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
  echo [FAIL] %LABEL% login HTTP %LOGIN_STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN_VALUE=%%T"
if "%TOKEN_VALUE%"=="" (
  echo [FAIL] %LABEL% login missing access_token
  exit /b 1
)

if "%LABEL%"=="client" set "CLIENT_TOKEN=%TOKEN_VALUE%"
if "%LABEL%"=="partner" set "PARTNER_TOKEN=%TOKEN_VALUE%"
if "%LABEL%"=="admin" set "ADMIN_TOKEN=%TOKEN_VALUE%"
echo [PASS] %LABEL% login OK
exit /b 0

:expect_status
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "EXPECTED=%~4"
set "EXPECTED_REASON=%~5"

set "RESP_FILE=%TEMP%\slice0_resp_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\slice0_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%URL%" > "%STATUS_FILE%"
set /p RESP_STATUS=<"%STATUS_FILE%"
if not "%RESP_STATUS%"=="%EXPECTED%" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS% expected %EXPECTED%
  type "%RESP_FILE%"
  exit /b 1
)

if "%EXPECTED%"=="401" (
  for /f "usebackq delims=" %%R in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); detail=data.get('detail') or {}; err=data.get('error') or {}; print(detail.get('reason_code') or err.get('reason_code') or data.get('reason_code',''))"`) do set "ACTUAL_REASON=%%R"
  if /i not "%ACTUAL_REASON%"=="%EXPECTED_REASON%" (
    echo [FAIL] %LABEL% reason_code %ACTUAL_REASON% expected %EXPECTED_REASON%
    type "%RESP_FILE%"
    exit /b 1
  )
)

echo [PASS] %LABEL%
exit /b 0
