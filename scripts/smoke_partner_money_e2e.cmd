@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%BASE_URL%/api/core/partner"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/v1/admin"
if "%CORE_ADMIN_FINANCE_URL%"=="" set "CORE_ADMIN_FINANCE_URL=%CORE_ADMIN_URL%/finance"
if "%CORE_ADMIN_AUDIT_URL%"=="" set "CORE_ADMIN_AUDIT_URL=%CORE_ADMIN_URL%/audit"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=partner"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "BASE_URL=%BASE_URL%"
call :log "CORE_PORTAL_URL=%CORE_PORTAL_URL%"
call :log "CORE_PARTNER_URL=%CORE_PARTNER_URL%"
call :log "CORE_ADMIN_URL=%CORE_ADMIN_URL%"
call :log "AUTH_URL=%AUTH_URL%"

set "STEP=0_seed_partner_money"
call :log "[%STEP%] call scripts\\seed_partner_money_e2e.cmd"
call scripts\seed_partner_money_e2e.cmd
if errorlevel 1 (
  call :fail "%STEP%" "seed failed"
  exit /b 1
)

set "STEP=1_partner_login"
call :log "[%STEP%] POST %AUTH_URL%/login"
set "HTTP_METHOD=POST"
set "HTTP_BODY="
set "LOGIN_PAYLOAD={""email"":""%PARTNER_EMAIL%"",""password"":""%PARTNER_PASSWORD%"",""portal"":""partner""}"
set "HTTP_BODY=!LOGIN_PAYLOAD!"
call :assert_http "%STEP%" "200" "%AUTH_URL%/login" "%TEMP%\partner_login.json"
set "PARTNER_TOKEN_FILE=%TEMP%\\partner_token.txt"
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TEMP%\\partner_login.json').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%PARTNER_TOKEN_FILE%').write_text(token); print(token)"`) do set "PARTNER_TOKEN=%%T"
if "!PARTNER_TOKEN!"=="" (
  call :fail "%STEP%" "missing partner token"
  exit /b 1
)

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

set "STEP=2_partner_verify"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %BASE_URL%/api/core/partner/auth/verify"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "204" "%BASE_URL%/api/core/partner/auth/verify" "%TEMP%\partner_verify.json" "%PARTNER_AUTH_HEADER%"

set "STEP=3_admin_login"
call :log "[%STEP%] POST %AUTH_URL%/login"
set "HTTP_METHOD=POST"
set "HTTP_BODY="
set "LOGIN_PAYLOAD={""email"":""%ADMIN_EMAIL%"",""password"":""%ADMIN_PASSWORD%"",""portal"":""admin""}"
set "HTTP_BODY=!LOGIN_PAYLOAD!"
call :assert_http "%STEP%" "200" "%AUTH_URL%/login" "%TEMP%\admin_login.json"
set "ADMIN_TOKEN_FILE=%TEMP%\\admin_token.txt"
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TEMP%\\admin_login.json').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%ADMIN_TOKEN_FILE%').write_text(token); print(token)"`) do set "ADMIN_TOKEN=%%T"
if "!ADMIN_TOKEN!"=="" (
  call :fail "%STEP%" "missing admin token"
  exit /b 1
)

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=4_portal_me"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "200" "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me_partner.json" "%PARTNER_AUTH_HEADER%"
call :expect_contains "%TEMP%\portal_me_partner.json" "\"partner\"" || (
  call :fail "%STEP%" "portal role missing"
  exit /b 1
)

set "STEP=5_partner_dashboard"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/dashboard"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "200" "%CORE_PARTNER_URL%/dashboard" "%TEMP%\partner_dashboard.json" "%PARTNER_AUTH_HEADER%"

set "STEP=6_partner_ledger"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/ledger"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "200" "%CORE_PARTNER_URL%/ledger?limit=5" "%TEMP%\partner_ledger.json" "%PARTNER_AUTH_HEADER%"

set "STEP=7_payout_preview"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/preview"
set "HTTP_METHOD=POST"
set "HTTP_BODY={}"
call :assert_http "%STEP%" "200" "%CORE_PARTNER_URL%/payouts/preview" "%TEMP%\partner_payout_preview.json" "%PARTNER_AUTH_HEADER%"

set "STEP=8_payout_request"
set "PAYOUT_PAYLOAD={""amount"":1000,""currency"":""RUB""}"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/request"
set "HTTP_METHOD=POST"
set "HTTP_BODY=!PAYOUT_PAYLOAD!"
call :assert_http "%STEP%" "201" "%CORE_PARTNER_URL%/payouts/request" "%TEMP%\partner_payout_request.json" "%PARTNER_AUTH_HEADER%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\partner_payout_request.json')).get('id',''))"`) do set "PAYOUT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\partner_payout_request.json')).get('correlation_id',''))"`) do set "CORRELATION_ID=%%t"
if "!PAYOUT_ID!"=="" (
  call :fail "%STEP%" "missing payout id"
  exit /b 1
)
if "!CORRELATION_ID!"=="" (
  call :fail "%STEP%" "missing correlation id"
  exit /b 1
)

set "STEP=9_admin_payout_queue"
call :require_token "%ADMIN_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_ADMIN_FINANCE_URL%/payouts"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "200" "%CORE_ADMIN_FINANCE_URL%/payouts" "%TEMP%\admin_payouts.json" "%ADMIN_AUTH_HEADER%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_payouts.json')); items=data.get('items') or []; print(any(item.get('payout_id')=='%PAYOUT_ID%' for item in items))"`) do set "PAYOUT_FOUND=%%t"
if /i not "!PAYOUT_FOUND!"=="True" (
  call :fail "%STEP%" "payout not found in admin queue"
  exit /b 1
)

set "STEP=10_admin_approve"
set "APPROVE_PAYLOAD={""reason"":""Smoke approval"",""correlation_id"":""!CORRELATION_ID!""}"
call :require_token "%ADMIN_TOKEN%" "%STEP%"
call :log "[%STEP%] POST %CORE_ADMIN_FINANCE_URL%/payouts/!PAYOUT_ID!/approve"
set "HTTP_METHOD=POST"
set "HTTP_BODY=!APPROVE_PAYLOAD!"
call :assert_http "%STEP%" "200" "%CORE_ADMIN_FINANCE_URL%/payouts/!PAYOUT_ID!/approve" "%TEMP%\admin_payout_approve.json" "%ADMIN_AUTH_HEADER%"

set "STEP=11_partner_payout_detail"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/payouts/!PAYOUT_ID!"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "200" "%CORE_PARTNER_URL%/payouts/!PAYOUT_ID!" "%TEMP%\partner_payout_detail.json" "%PARTNER_AUTH_HEADER%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; status=json.load(open(r'%TEMP%\\partner_payout_detail.json')).get('status',''); print(status in {'APPROVED','PAID'})"`) do set "PAYOUT_STATUS_OK=%%t"
if /i not "!PAYOUT_STATUS_OK!"=="True" (
  call :fail "%STEP%" "payout status not approved"
  exit /b 1
)

set "STEP=12_admin_audit"
call :require_token "%ADMIN_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_ADMIN_AUDIT_URL%?correlation_id=!CORRELATION_ID!"
set "HTTP_METHOD=GET"
set "HTTP_BODY="
call :assert_http "%STEP%" "200" "%CORE_ADMIN_AUDIT_URL%?correlation_id=!CORRELATION_ID!" "%TEMP%\admin_audit.json" "%ADMIN_AUTH_HEADER%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_audit.json')); items=data.get('items') or []; print(len(items) >= 2)"`) do set "AUDIT_OK=%%t"
if /i not "!AUDIT_OK!"=="True" (
  call :fail "%STEP%" "audit entries missing"
  exit /b 1
)

echo E2E_PARTNER_MONEY: PASS
echo E2E_PARTNER_MONEY: PASS>>"%LOG_FILE%"
exit /b 0

:fail
set "FAILED_STEP=%~1"
set "FAILED_MSG=%~2"
echo E2E_PARTNER_MONEY: FAIL
echo E2E_PARTNER_MONEY: FAIL>>"%LOG_FILE%"
if not "%FAILED_STEP%"=="" (
  echo [%FAILED_STEP%] %FAILED_MSG%>>"%LOG_FILE%"
)
exit /b 1

:log
set "LOG_MESSAGE=%~1"
echo %LOG_MESSAGE%
echo %LOG_MESSAGE%>>"%LOG_FILE%"
exit /b 0

:append_response
set "RESP_FILE=%~1"
if exist "%RESP_FILE%" (
  echo ---- response from %RESP_FILE% ---->>"%LOG_FILE%"
  type "%RESP_FILE%">>"%LOG_FILE%"
  echo.>>"%LOG_FILE%"
)
exit /b 0

:assert_http
set "STEP_NAME=%~1"
set "EXPECTED=%~2"
set "URL=%~3"
set "OUT=%~4"
set "CURL_HEADERS="
shift
shift
shift
shift
:assert_http_headers
if "%~1"=="" goto assert_http_request
set "CURL_HEADERS=!CURL_HEADERS! -H \"%~1\""
shift
goto assert_http_headers
:assert_http_request
if "!HTTP_METHOD!"=="" set "HTTP_METHOD=GET"
if "!HTTP_METHOD!"=="GET" (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X GET !CURL_HEADERS! "%URL%"`) do set "LAST_STATUS=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X !HTTP_METHOD! !CURL_HEADERS! -H "Content-Type: application/json" -d "!HTTP_BODY!" "%URL%"`) do set "LAST_STATUS=%%c"
)
call :append_response "%OUT%"
if "!LAST_STATUS!"=="%EXPECTED%" exit /b 0
call :fail "%STEP_NAME%" "expected %EXPECTED% got !LAST_STATUS!"
exit /b 1

:expect_contains
set "FILE=%~1"
set "SUB=%~2"
findstr /c:"%SUB%" "%FILE%" >nul
if errorlevel 1 exit /b 1
exit /b 0

:extract_json_field
set "FILE=%~1"
set "FIELD=%~2"
set "OUTVAR=%~3"
set "FOUND="
for /f "usebackq delims=" %%l in (`findstr /r /c:"\"%FIELD%\"[ ]*:[ ]*\"*[^\",}]*" "%FILE%"`) do (
  set "FOUND=%%l"
  goto :extract_json_field_done
)
:extract_json_field_done
if "%FOUND%"=="" (
  set "%OUTVAR%="
  exit /b 0
)
for /f "tokens=2 delims=:" %%a in ("%FOUND%") do set "VALUE=%%a"
set "VALUE=%VALUE: =%"
set "VALUE=%VALUE:~0,-1%"
set "VALUE=%VALUE:\"=%"
set "%OUTVAR%=%VALUE%"
exit /b 0

:require_token
set "TOKEN_VALUE=%~1"
set "TOKEN_STEP=%~2"
if "%TOKEN_VALUE%"=="" (
  call :fail "%TOKEN_STEP%" "missing auth token"
  exit /b 1
)
exit /b 0
