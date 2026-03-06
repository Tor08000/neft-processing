@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_NAME=smoke_payout_closed_loop_e2e"

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"

if not exist logs mkdir logs
set "LOG_FILE=logs\\%SCRIPT_NAME%_%DATE:/=-%_%TIME::=-%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "Seed data"
call scripts\\seed_e2e.cmd
if errorlevel 1 call :fail "seed"

set "STEP=partner_login"
set "LOGIN_PAYLOAD={""email"":""%PARTNER_EMAIL%"",""password"":""%PARTNER_PASSWORD%""}"
call :log "[%STEP%] POST %AUTH_URL%/login"
call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\\partner_login.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\partner_login.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :extract_json_field "%TEMP%\\partner_login.json" "access_token" PARTNER_TOKEN
if "!PARTNER_TOKEN!"=="" call :fail "%STEP%"

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"

set "STEP=partner_me"
call :log "[%STEP%] GET %CORE_URL%/partner/me"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_URL%/partner/me" "%TEMP%\\partner_me.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\partner_me.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\partner_me.json')); print(data.get('org',{}).get('id',''))"`) do set "ORG_ID=%%t"
if "!ORG_ID!"=="" call :fail "%STEP%"

set "STEP=admin_token"
call :log "[%STEP%] admin token"
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "ADMIN_TOKEN=%%T"
if "!ADMIN_TOKEN!"=="" call :fail "%STEP%"
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"

set "STEP=seed_settlement"
call :log "[%STEP%] POST %CORE_URL%/v1/admin/settlement/periods/calculate"
for /f "usebackq delims=" %%p in (`
  python -c "import datetime,uuid,os; now=datetime.datetime.now(datetime.timezone.utc); start=(now-datetime.timedelta(days=7)).isoformat(); end=now.isoformat(); payload={'partner_id':os.environ.get('ORG_ID',''),'currency':'RUB','period_start':start,'period_end':end,'idempotency_key':str(uuid.uuid4())}; import json; print(json.dumps(payload))"
`) do set "SETTLEMENT_PAYLOAD=%%p"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_URL%/v1/admin/settlement/periods/calculate" "!SETTLEMENT_PAYLOAD!" "%TEMP%\\settlement_period.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\settlement_period.json"
if not "!LAST_STATUS!"=="200" if not "!LAST_STATUS!"=="201" call :fail "%STEP%"

set "STEP=payout_request"
set "PAYOUT_PAYLOAD={""amount"":1000,""currency"":""RUB""}"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :log "[%STEP%] POST %CORE_URL%/partner/payouts/request"
call :http_post "%CORE_URL%/partner/payouts/request" "!PAYOUT_PAYLOAD!" "%TEMP%\\partner_payout_request.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\partner_payout_request.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :extract_json_field "%TEMP%\\partner_payout_request.json" "id" PAYOUT_ID
call :extract_json_field "%TEMP%\\partner_payout_request.json" "correlation_id" CORRELATION_ID
if "!PAYOUT_ID!"=="" call :fail "%STEP%"
if "!CORRELATION_ID!"=="" call :fail "%STEP%"

set "STEP=admin_payout_queue"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :log "[%STEP%] GET %CORE_URL%/v1/admin/finance/payouts"
call :http_get "%CORE_URL%/v1/admin/finance/payouts" "%TEMP%\\admin_payouts.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\admin_payouts.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_payouts.json')); items=data.get('items') or []; match=[item for item in items if str(item.get('payout_id'))=='%PAYOUT_ID%']; print(match[0].get('payout_id','') if match else '')"`) do set "FOUND_PAYOUT_ID=%%t"
if "!FOUND_PAYOUT_ID!"=="" call :fail "%STEP%"

set "STEP=admin_payout_detail"
call :log "[%STEP%] GET %CORE_URL%/v1/admin/finance/payouts/%PAYOUT_ID%"
call :http_get "%CORE_URL%/v1/admin/finance/payouts/%PAYOUT_ID%" "%TEMP%\\admin_payout_detail.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\admin_payout_detail.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_payout_detail.json')); print(data.get('correlation_id',''))"`) do set "DETAIL_CORRELATION=%%t"
if not "!DETAIL_CORRELATION!"=="!CORRELATION_ID!" call :fail "%STEP%"

set "STEP=admin_payout_approve"
set "APPROVE_PAYLOAD={""reason"":""E2E approve"",""correlation_id"":""%CORRELATION_ID%""}"
call :log "[%STEP%] POST %CORE_URL%/v1/admin/finance/payouts/%PAYOUT_ID%/approve"
call :http_post "%CORE_URL%/v1/admin/finance/payouts/%PAYOUT_ID%/approve" "!APPROVE_PAYLOAD!" "%TEMP%\\admin_payout_approve.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\admin_payout_approve.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=partner_payout_history"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :log "[%STEP%] GET %CORE_URL%/partner/payouts/history"
call :http_get "%CORE_URL%/partner/payouts/history" "%TEMP%\\partner_payout_history.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\partner_payout_history.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\partner_payout_history.json')); items=data.get('requests') or []; match=[item for item in items if str(item.get('id'))=='%PAYOUT_ID%']; print(match[0].get('status','') if match else '')"`) do set "HISTORY_STATUS=%%t"
if "!HISTORY_STATUS!"=="" call :fail "%STEP%"

set "STEP=admin_audit_chain"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :log "[%STEP%] GET %CORE_URL%/v1/admin/audit/%CORRELATION_ID%"
call :http_get "%CORE_URL%/v1/admin/audit/%CORRELATION_ID%" "%TEMP%\\admin_audit_chain.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\\admin_audit_chain.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\admin_audit_chain.json')); items=data.get('items') or data.get('events') or []; print(len(items))"`) do set "CHAIN_COUNT=%%t"
if "!CHAIN_COUNT!"=="0" call :fail "%STEP%"

call :log "E2E_PAYOUT_CLOSED_LOOP: PASS"
echo E2E_PAYOUT_CLOSED_LOOP: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_PAYOUT_CLOSED_LOOP: FAIL at %FAILED_STEP%"
echo E2E_PAYOUT_CLOSED_LOOP: FAIL at %FAILED_STEP%
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
