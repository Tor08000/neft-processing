@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM Smoke: mounted UX gating states (client/partner/admin)
REM This script aggregates only owner-backed gating contours that already have
REM real runtime flows.

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ADMIN_VERIFY=%CORE_API_BASE%%CORE_BASE%/admin/auth/verify"
set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "CLIENT_LOGIN_FILE=%TEMP%\gating_states_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\gating_states_client_login_body_%RANDOM%.json"
set "ADMIN_VERIFY_FILE=%TEMP%\gating_states_admin_verify_%RANDOM%.txt"
set "FORBIDDEN_FILE=%TEMP%\gating_states_admin_forbidden_%RANDOM%.json"

call :wait_for_status "%AUTH_HOST_BASE%/health" "200" 20 2 || goto :fail
call :wait_for_status "%CORE_API_BASE%/health" "200" 20 2 || goto :fail

echo [1/6] Verify auth wrong-portal and forbidden-role gating...
for /f "usebackq delims=" %%T in (`scripts\get_admin_token.cmd`) do set "ADMIN_TOKEN=%%T"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] Could not fetch admin token.
  goto :fail
)
python -c "import json; from pathlib import Path; Path(r'%CLIENT_LOGIN_BODY%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%', 'password': r'%CLIENT_PASSWORD%', 'portal': 'client'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%CLIENT_LOGIN_BODY%" "200" "%CLIENT_LOGIN_FILE%" || goto :fail
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] Could not fetch client token.
  goto :fail
)
call :http_request "GET" "%CORE_ADMIN_VERIFY%" "Authorization: Bearer %ADMIN_TOKEN%" "" "204" "%ADMIN_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ADMIN_VERIFY%" "Authorization: Bearer %CLIENT_TOKEN%" "" "401" "%FORBIDDEN_FILE%" || goto :fail
for /f "usebackq delims=" %%R in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%FORBIDDEN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); detail=data.get('detail') if isinstance(data.get('detail'), dict) else {}; err=data.get('error') if isinstance(data.get('error'), dict) else {}; msg=data.get('message') if isinstance(data.get('message'), dict) else {}; reason=detail.get('reason_code') or err.get('reason_code') or msg.get('reason_code') or data.get('reason_code') or ''; print(reason)"`) do set "WRONG_PORTAL_REASON=%%R"
if /i not "%WRONG_PORTAL_REASON%"=="TOKEN_WRONG_PORTAL" (
  echo [FAIL] Wrong-portal admin gate returned unexpected reason: %WRONG_PORTAL_REASON%
  if exist "%FORBIDDEN_FILE%" type "%FORBIDDEN_FILE%"
  goto :fail
)
echo [OK] Auth wrong-portal and forbidden-role gating.

echo [2/6] Verify client activation/onboarding gating...
call "%~dp0smoke_onboarding_e2e.cmd"
if errorlevel 1 goto :fail

echo [3/6] Verify client plan/paywall/active mounted gating...
call "%~dp0smoke_client_active_e2e.cmd"
if errorlevel 1 goto :fail

echo [4/6] Verify client overdue/payment-required gating...
call "%~dp0smoke_commerce_overdue_unblock_e2e.cmd"
if errorlevel 1 goto :fail

echo [5/6] Verify partner onboarding/legal-checklist gating...
call "%~dp0smoke_partner_onboarding.cmd"
if errorlevel 1 goto :fail

echo [6/6] Verify partner legal/payout-blocked gating...
call "%~dp0smoke_partner_legal_payout_e2e.cmd"
if errorlevel 1 goto :fail

echo [SMOKE] UX gating states completed.
goto :cleanup_success

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
if "%OUT%"=="" set "OUT=%TEMP%\gating_states_resp_%RANDOM%.json"
set "STATUS="
if /I "%METHOD%"=="GET" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" "%URL%" 2^>nul`) do set "STATUS=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -H "%HEADER%" "%URL%" 2^>nul`) do set "STATUS=%%c"
  )
)
if /I "%METHOD%"=="POST" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" -X POST "%URL%" 2^>nul`) do set "STATUS=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" -X POST "%URL%" 2^>nul`) do set "STATUS=%%c"
  )
)
if /I "%STATUS%"=="%EXPECTED%" exit /b 0
echo [FAIL] %METHOD% %URL% expected %EXPECTED% got %STATUS%
if exist "%OUT%" type "%OUT%"
exit /b 1

:wait_for_status
set "WAIT_URL=%~1"
set "WAIT_EXPECTED=%~2"
set "WAIT_ATTEMPTS=%~3"
set "WAIT_DELAY=%~4"
if "%WAIT_ATTEMPTS%"=="" set "WAIT_ATTEMPTS=15"
if "%WAIT_DELAY%"=="" set "WAIT_DELAY=2"
set "WAIT_CODE="
for /l %%i in (1,1,%WAIT_ATTEMPTS%) do (
  for /f "usebackq tokens=*" %%c in (`curl -s -S -o NUL -w "%%{http_code}" "%WAIT_URL%" 2^>nul`) do (
    set "WAIT_CODE=%%c"
    if "%%c"=="%WAIT_EXPECTED%" exit /b 0
  )
  if not "%%i"=="%WAIT_ATTEMPTS%" powershell -NoProfile -Command "Start-Sleep -Seconds %WAIT_DELAY%" >nul
)
echo [FAIL] %WAIT_URL% did not reach %WAIT_EXPECTED%, last code=%WAIT_CODE%
exit /b 1

:cleanup_success
del /q "%CLIENT_LOGIN_FILE%" 2>nul
del /q "%CLIENT_LOGIN_BODY%" 2>nul
del /q "%ADMIN_VERIFY_FILE%" 2>nul
del /q "%FORBIDDEN_FILE%" 2>nul
exit /b 0

:fail
del /q "%CLIENT_LOGIN_FILE%" 2>nul
del /q "%CLIENT_LOGIN_BODY%" 2>nul
del /q "%ADMIN_VERIFY_FILE%" 2>nul
del /q "%FORBIDDEN_FILE%" 2>nul
echo [SMOKE] UX gating states failed.
exit /b 1
