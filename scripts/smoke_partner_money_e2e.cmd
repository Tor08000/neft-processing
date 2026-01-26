@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%BASE_URL%/api/core/partner"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/admin"
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
if errorlevel 1 call :fail "%STEP%"

set "STEP=1_partner_login"
call :log "[%STEP%] POST %AUTH_URL%/login"
set "HTTP_HEADER="
set "LOGIN_PAYLOAD={""email"":""%PARTNER_EMAIL%"",""password"":""%PARTNER_PASSWORD%"",""portal"":""partner""}"
call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\partner_login.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_login.json"
if "!LAST_STATUS!"=="422" (
  type "%TEMP%\partner_login.json"
)
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
set "PARTNER_TOKEN_FILE=%TEMP%\\partner_token.txt"
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TEMP%\\partner_login.json').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%PARTNER_TOKEN_FILE%').write_text(token); print(token)"`) do set "PARTNER_TOKEN=%%T"
if "!PARTNER_TOKEN!"=="" call :fail "%STEP%"

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

set "STEP=2_partner_verify"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %BASE_URL%/api/core/partner/auth/verify"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%BASE_URL%/api/core/partner/auth/verify" "%TEMP%\partner_verify.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_verify.json"
if not "!LAST_STATUS!"=="204" call :fail "%STEP%"

set "STEP=3_admin_login"
call :log "[%STEP%] POST %AUTH_URL%/login"
set "HTTP_HEADER="
set "LOGIN_PAYLOAD={""email"":""%ADMIN_EMAIL%"",""password"":""%ADMIN_PASSWORD%"",""portal"":""admin""}"
call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\admin_login.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\admin_login.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
set "ADMIN_TOKEN_FILE=%TEMP%\\admin_token.txt"
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TEMP%\\admin_login.json').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%ADMIN_TOKEN_FILE%').write_text(token); print(token)"`) do set "ADMIN_TOKEN=%%T"
if "!ADMIN_TOKEN!"=="" call :fail "%STEP%"

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=4_portal_me"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me_partner.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_me_partner.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_partner.json" "\"partner\"" || call :fail "%STEP%"

set "STEP=5_partner_dashboard"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/dashboard"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/dashboard" "%TEMP%\partner_dashboard.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_dashboard.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=6_partner_ledger"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/ledger"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/ledger?limit=5" "%TEMP%\partner_ledger.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_ledger.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=7_payout_preview"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/preview"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/payouts/preview" "{}" "%TEMP%\partner_payout_preview.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_payout_preview.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=8_payout_request"
set "PAYOUT_PAYLOAD={""amount"":1000,""currency"":""RUB""}"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/request"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/payouts/request" "!PAYOUT_PAYLOAD!" "%TEMP%\partner_payout_request.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_payout_request.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\partner_payout_request.json')).get('id',''))"`) do set "PAYOUT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\partner_payout_request.json')).get('correlation_id',''))"`) do set "CORRELATION_ID=%%t"
if "!PAYOUT_ID!"=="" call :fail "%STEP%"
if "!CORRELATION_ID!"=="" call :fail "%STEP%"

set "STEP=9_admin_payout_queue"
call :require_token "%ADMIN_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_ADMIN_FINANCE_URL%/payouts"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_get "%CORE_ADMIN_FINANCE_URL%/payouts" "%TEMP%\admin_payouts.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\admin_payouts.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_payouts.json')); items=data.get('items') or []; print(any(item.get('payout_id')=='%PAYOUT_ID%' for item in items))"`) do set "PAYOUT_FOUND=%%t"
if /i not "!PAYOUT_FOUND!"=="True" call :fail "%STEP%"

set "STEP=10_admin_approve"
set "APPROVE_PAYLOAD={""reason"":""Smoke approval"",""correlation_id"":""!CORRELATION_ID!""}"
call :require_token "%ADMIN_TOKEN%" "%STEP%"
call :log "[%STEP%] POST %CORE_ADMIN_FINANCE_URL%/payouts/!PAYOUT_ID!/approve"
call :http_post "%CORE_ADMIN_FINANCE_URL%/payouts/!PAYOUT_ID!/approve" "!APPROVE_PAYLOAD!" "%TEMP%\admin_payout_approve.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\admin_payout_approve.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=11_partner_payout_detail"
call :require_token "%PARTNER_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/payouts/!PAYOUT_ID!"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/payouts/!PAYOUT_ID!" "%TEMP%\partner_payout_detail.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_payout_detail.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; status=json.load(open(r'%TEMP%\\partner_payout_detail.json')).get('status',''); print(status in {'APPROVED','PAID'})"`) do set "PAYOUT_STATUS_OK=%%t"
if /i not "!PAYOUT_STATUS_OK!"=="True" call :fail "%STEP%"

set "STEP=12_admin_audit"
call :require_token "%ADMIN_TOKEN%" "%STEP%"
call :log "[%STEP%] GET %CORE_ADMIN_AUDIT_URL%?correlation_id=!CORRELATION_ID!"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_get "%CORE_ADMIN_AUDIT_URL%?correlation_id=!CORRELATION_ID!" "%TEMP%\admin_audit.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\admin_audit.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_audit.json')); items=data.get('items') or []; print(len(items) >= 2)"`) do set "AUDIT_OK=%%t"
if /i not "!AUDIT_OK!"=="True" call :fail "%STEP%"

call :log "E2E_PARTNER_MONEY: PASS"
echo E2E_PARTNER_MONEY: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_PARTNER_MONEY: FAIL at %FAILED_STEP%"
echo E2E_PARTNER_MONEY: FAIL at %FAILED_STEP%
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

:http_get
set "URL=%~1"
set "OUT=%~2"
if "!HTTP_HEADER!"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" "%URL%"`) do set "LAST_STATUS=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -H "!HTTP_HEADER!" "%URL%"`) do set "LAST_STATUS=%%c"
)
exit /b 0

:http_post
set "URL=%~1"
set "BODY=%~2"
set "OUT=%~3"
set "REQ_FILE=%TEMP%\\%SCRIPT_NAME%_req.json"
> "!REQ_FILE!" echo(!BODY!
if "!HTTP_HEADER!"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X POST -H "Content-Type: application/json" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X POST -H "!HTTP_HEADER!" -H "Content-Type: application/json" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
)
exit /b 0

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
  call :fail "%TOKEN_STEP%"
)
exit /b 0
