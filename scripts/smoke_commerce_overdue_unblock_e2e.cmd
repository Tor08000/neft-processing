@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_commerce_overdue_unblock_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_CLIENT_URL%"=="" set "CORE_CLIENT_URL=%BASE_URL%/api/core/client"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/v1/admin"

if "%PLAN_CODE%"=="" set "PLAN_CODE=CONTROL"
if "%PLAN_VERSION%"=="" set "PLAN_VERSION=1"

if "%PAYER_NAME%"=="" set "PAYER_NAME=ООО Ромашка"
if "%PAYER_INN%"=="" set "PAYER_INN=7700000000"
if "%BANK_REF%"=="" set "BANK_REF=SMOKE-REF-1"

if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] ADMIN_TOKEN is required.
  exit /b 1
)

if "%CLIENT_TOKEN%"=="" (
  if "%CLIENT_EMAIL%"=="" (
    echo [FAIL] CLIENT_EMAIL is required when CLIENT_TOKEN is not set.
    exit /b 1
  )
  if "%CLIENT_PASSWORD%"=="" (
    echo [FAIL] CLIENT_PASSWORD is required when CLIENT_TOKEN is not set.
    exit /b 1
  )
)

for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set "RUN_TS=%%t"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\smoke_commerce_unblock_%RUN_TS%.log"

set "TEMP_DIR=%TEMP%\%SCRIPT_NAME%_%RUN_TS%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

set "HTTP_HEADER="
set "LAST_STATUS="
set "ORG_ID=%ORG_ID%"
set "ENT_HASH_BEFORE="
set "ENT_HASH_AFTER="
set "ENT_COMP_BEFORE="
set "ENT_COMP_AFTER="
set "SUB_STATUS_BEFORE="
set "SUB_STATUS_AFTER="
set "INVOICE_ID="
set "INVOICE_TOTAL="
set "PAYMENT_INTAKE_ID="

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=0_health"
call :log "[%STEP%] GET %BASE_URL%/api/core/health"
set "HTTP_HEADER="
call :http_get "%BASE_URL%/api/core/health" "%TEMP_DIR%\health.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\health.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :expect_contains "%TEMP_DIR%\health.json" "\"status\":\"ok\"" || call :fail "%STEP%"

set "STEP=1_client_login"
if "%CLIENT_TOKEN%"=="" (
  call :log "[%STEP%] POST %AUTH_URL%/login"
  set "LOGIN_PAYLOAD={""email"":""%CLIENT_EMAIL%"",""password"":""%CLIENT_PASSWORD%""}"
  call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP_DIR%\client_login.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP_DIR%\client_login.json"
  call :expect_status "%STEP%" "200" || call :fail "%STEP%"
  call :extract_json_field "%TEMP_DIR%\client_login.json" "access_token" CLIENT_TOKEN
  if "!CLIENT_TOKEN!"=="" call :fail "%STEP%"
)

set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP_DIR%\portal_me.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\portal_me.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\portal_me.json" "org_id" ORG_ID
call :extract_json_field "%TEMP_DIR%\portal_me.json" "entitlements_hash" ENT_HASH_BEFORE
call :extract_json_field "%TEMP_DIR%\portal_me.json" "entitlements_computed_at" ENT_COMP_BEFORE
call :extract_json_field "%TEMP_DIR%\portal_me.json" "subscription.status" SUB_STATUS_BEFORE
if "!ORG_ID!"=="" call :fail "%STEP%"
call :log "ORG_ID=!ORG_ID!"
call :log "ENT_HASH_BEFORE=!ENT_HASH_BEFORE!"
call :log "SUB_STATUS_BEFORE=!SUB_STATUS_BEFORE!"

set "STEP=2_ensure_subscription_active"
if /i not "!SUB_STATUS_BEFORE!"=="ACTIVE" (
  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/plan"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  set "PLAN_PAYLOAD={""plan_code"":""%PLAN_CODE%"",""plan_version"":%PLAN_VERSION%,""billing_cycle"":""MONTHLY"",""status"":""ACTIVE"",""reason"":""smoke_commerce_overdue_setup""}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/plan" "!PLAN_PAYLOAD!" "%TEMP_DIR%\plan_update.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP_DIR%\plan_update.json"
  call :expect_status "%STEP%" "200" || call :fail "%STEP%"

  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute"
  set "ENTITLEMENTS_PAYLOAD={}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute" "!ENTITLEMENTS_PAYLOAD!" "%TEMP_DIR%\entitlements_recompute_setup.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP_DIR%\entitlements_recompute_setup.json"
  call :expect_status "%STEP%" "200" || call :fail "%STEP%"
)

call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP_DIR%\portal_me_active.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\portal_me_active.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\portal_me_active.json" "subscription.status" SUB_STATUS_BEFORE
if /i not "!SUB_STATUS_BEFORE!"=="ACTIVE" call :fail "%STEP%"

set "STEP=3_force_overdue"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/status"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "STATUS_PAYLOAD={""status"":""OVERDUE"",""reason"":""smoke_commerce_overdue""}"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/status" "!STATUS_PAYLOAD!" "%TEMP_DIR%\status_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\status_overdue.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"

call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute"
set "ENTITLEMENTS_PAYLOAD={}"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute" "!ENTITLEMENTS_PAYLOAD!" "%TEMP_DIR%\entitlements_recompute_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\entitlements_recompute_overdue.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"

call :log "[%STEP%] POST %CORE_CLIENT_URL%/exports/jobs (expect 403)"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
set "EXPORT_PAYLOAD={""report_type"":""CARDS"",""format"":""CSV"",""filters"":{}}"
call :http_post "%CORE_CLIENT_URL%/exports/jobs" "!EXPORT_PAYLOAD!" "%TEMP_DIR%\export_blocked.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\export_blocked.json"
call :expect_status "%STEP%" "403" || call :fail "%STEP%"
call :expect_contains "%TEMP_DIR%\export_blocked.json" "billing_soft_blocked" || (
  call :expect_contains "%TEMP_DIR%\export_blocked.json" "subscription_overdue" || call :fail "%STEP%"
)

set "STEP=4_find_or_generate_invoice"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/billing/generate"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "GENERATE_PAYLOAD={""org_id"":""!ORG_ID!"",""reason"":""smoke_invoice_generate""}"
call :http_post "%CORE_ADMIN_URL%/billing/generate" "!GENERATE_PAYLOAD!" "%TEMP_DIR%\invoice_generate.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\invoice_generate.json"
if "!LAST_STATUS!"=="200" (
  call :extract_json_field "%TEMP_DIR%\invoice_generate.json" "invoice_id" INVOICE_ID
  if "!INVOICE_ID!"=="" call :extract_json_field "%TEMP_DIR%\invoice_generate.json" "id" INVOICE_ID
)
if "!INVOICE_ID!"=="" if "!LAST_STATUS!"=="201" (
  call :extract_json_field "%TEMP_DIR%\invoice_generate.json" "invoice_id" INVOICE_ID
  if "!INVOICE_ID!"=="" call :extract_json_field "%TEMP_DIR%\invoice_generate.json" "id" INVOICE_ID
)
if "!INVOICE_ID!"=="" if "!LAST_STATUS!"=="202" (
  call :extract_json_field "%TEMP_DIR%\invoice_generate.json" "invoice_id" INVOICE_ID
  if "!INVOICE_ID!"=="" call :extract_json_field "%TEMP_DIR%\invoice_generate.json" "id" INVOICE_ID
)
if "!INVOICE_ID!"=="" if "!LAST_STATUS!"=="200" (
  for /f "usebackq delims=" %%i in (`python -c "import json; d=json.load(open(r'%TEMP_DIR%\\invoice_generate.json')); ids=d.get('created_ids') or []; print(ids[0] if ids else '')"`) do set "INVOICE_ID=%%i"
)
if "!INVOICE_ID!"=="" if "!LAST_STATUS!"=="201" (
  for /f "usebackq delims=" %%i in (`python -c "import json; d=json.load(open(r'%TEMP_DIR%\\invoice_generate.json')); ids=d.get('created_ids') or []; print(ids[0] if ids else '')"`) do set "INVOICE_ID=%%i"
)
if "!INVOICE_ID!"=="" if "!LAST_STATUS!"=="202" (
  for /f "usebackq delims=" %%i in (`python -c "import json; d=json.load(open(r'%TEMP_DIR%\\invoice_generate.json')); ids=d.get('created_ids') or []; print(ids[0] if ids else '')"`) do set "INVOICE_ID=%%i"
)
if "!INVOICE_ID!"=="" (
  call :log "[%STEP%] GET %CORE_CLIENT_URL%/invoices?limit=5"
  set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
  call :http_get "%CORE_CLIENT_URL%/invoices?limit=5" "%TEMP_DIR%\invoices_list.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP_DIR%\invoices_list.json"
  call :expect_status "%STEP%" "200" || call :fail "%STEP%"
  for /f "usebackq delims=" %%i in (`python -c "import json; d=json.load(open(r'%TEMP_DIR%\\invoices_list.json')); items=d.get('items') or d.get('results') or d.get('data') or [];\nfor item in items:\n  if item.get('status') in ('ISSUED','OVERDUE'):\n    total=item.get('total') or item.get('amount') or item.get('total_amount') or '';\n    print(f\"{item.get('id','')}|{total}\");\n    break"`) do set "INVOICE_PAIR=%%i"
  for /f "tokens=1,2 delims=|" %%a in ("!INVOICE_PAIR!") do (
    set "INVOICE_ID=%%a"
    set "INVOICE_TOTAL=%%b"
  )
)

if "!INVOICE_ID!"=="" call :fail "%STEP%"
call :log "INVOICE_ID=!INVOICE_ID!"

if "!INVOICE_TOTAL!"=="" (
  call :log "[%STEP%] GET %CORE_CLIENT_URL%/invoices/!INVOICE_ID!"
  set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
  call :http_get "%CORE_CLIENT_URL%/invoices/!INVOICE_ID!" "%TEMP_DIR%\invoice_detail.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP_DIR%\invoice_detail.json"
  call :expect_status "%STEP%" "200" || call :fail "%STEP%"
  call :extract_json_field "%TEMP_DIR%\invoice_detail.json" "total" INVOICE_TOTAL
  if "!INVOICE_TOTAL!"=="" call :extract_json_field "%TEMP_DIR%\invoice_detail.json" "amount" INVOICE_TOTAL
)

if "%PAYMENT_AMOUNT%"=="" set "PAYMENT_AMOUNT=!INVOICE_TOTAL!"
if "!PAYMENT_AMOUNT!"=="" call :fail "%STEP%"

set "STEP=5_payment_intake"
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-ddTHH:mm:ssZ"`) do set "PAID_AT=%%t"
call :log "[%STEP%] POST %CORE_CLIENT_URL%/invoices/!INVOICE_ID!/payment-intakes"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
set "PAYMENT_PAYLOAD={""amount"":!PAYMENT_AMOUNT!,""currency"":""RUB"",""payer_name"":""%PAYER_NAME%"",""payer_inn"":""%PAYER_INN%"",""bank_reference"":""%BANK_REF%"",""paid_at_claimed"":""!PAID_AT!"",""comment"":""smoke_e2e_payment_intake""}"
call :http_post "%CORE_CLIENT_URL%/invoices/!INVOICE_ID!/payment-intakes" "!PAYMENT_PAYLOAD!" "%TEMP_DIR%\payment_intake.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\payment_intake.json"
call :expect_status "%STEP%" "200" "201" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\payment_intake.json" "id" PAYMENT_INTAKE_ID
if "!PAYMENT_INTAKE_ID!"=="" call :extract_json_field "%TEMP_DIR%\payment_intake.json" "payment_intake_id" PAYMENT_INTAKE_ID
if "!PAYMENT_INTAKE_ID!"=="" call :fail "%STEP%"

set "STEP=6_admin_approve"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/billing/payment-intakes/!PAYMENT_INTAKE_ID!/approve"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "APPROVE_PAYLOAD={""reason"":""smoke_e2e_approve""}"
call :http_post "%CORE_ADMIN_URL%/billing/payment-intakes/!PAYMENT_INTAKE_ID!/approve" "!APPROVE_PAYLOAD!" "%TEMP_DIR%\payment_approve.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\payment_approve.json"
call :expect_status "%STEP%" "200" "201" || call :fail "%STEP%"

call :log "[%STEP%] GET %CORE_CLIENT_URL%/invoices/!INVOICE_ID!"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_CLIENT_URL%/invoices/!INVOICE_ID!" "%TEMP_DIR%\invoice_after.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\invoice_after.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :expect_contains "%TEMP_DIR%\invoice_after.json" "PAID" || call :fail "%STEP%"

call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP_DIR%\portal_me_after.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\portal_me_after.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\portal_me_after.json" "subscription.status" SUB_STATUS_AFTER
call :extract_json_field "%TEMP_DIR%\portal_me_after.json" "entitlements_hash" ENT_HASH_AFTER
call :extract_json_field "%TEMP_DIR%\portal_me_after.json" "entitlements_computed_at" ENT_COMP_AFTER
if /i not "!SUB_STATUS_AFTER!"=="ACTIVE" call :fail "%STEP%"

set "ENT_UPDATED=0"
if not "!ENT_HASH_BEFORE!"=="" if not "!ENT_HASH_AFTER!"=="" if /i not "!ENT_HASH_BEFORE!"=="!ENT_HASH_AFTER!" set "ENT_UPDATED=1"
if "!ENT_UPDATED!"=="0" if not "!ENT_COMP_BEFORE!"=="" if not "!ENT_COMP_AFTER!"=="" if /i not "!ENT_COMP_BEFORE!"=="!ENT_COMP_AFTER!" set "ENT_UPDATED=1"
if "!ENT_UPDATED!"=="0" call :fail "%STEP%"

set "STEP=7_exports_unblocked"
call :log "[%STEP%] POST %CORE_CLIENT_URL%/exports/jobs"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
set "EXPORT_PAYLOAD={""report_type"":""CARDS"",""format"":""CSV"",""filters"":{}}"
call :http_post "%CORE_CLIENT_URL%/exports/jobs" "!EXPORT_PAYLOAD!" "%TEMP_DIR%\export_unblocked.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\export_unblocked.json"
call :expect_status "%STEP%" "201" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\export_unblocked.json" "id" EXPORT_JOB_ID
if "!EXPORT_JOB_ID!"=="" call :extract_json_field "%TEMP_DIR%\export_unblocked.json" "job_id" EXPORT_JOB_ID
if "!EXPORT_JOB_ID!"=="" call :log "[%STEP%] WARN: export job id not found"

set "STEP=8_cleanup"
call :cleanup

call :log "E2E_COMMERCE_UNBLOCK: PASS"
echo E2E_COMMERCE_UNBLOCK: PASS
exit /b 0

:cleanup
if "!ORG_ID!"=="" exit /b 0
call :log "[%STEP%] Cleanup: set status ACTIVE"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "STATUS_PAYLOAD={""status"":""ACTIVE"",""reason"":""smoke_commerce_cleanup""}"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/status" "!STATUS_PAYLOAD!" "%TEMP_DIR%\status_active.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\status_active.json"

call :log "[%STEP%] Cleanup: recompute entitlements"
set "ENTITLEMENTS_PAYLOAD={}"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute" "!ENTITLEMENTS_PAYLOAD!" "%TEMP_DIR%\entitlements_recompute_cleanup.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\entitlements_recompute_cleanup.json"
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_COMMERCE_UNBLOCK: FAIL at %FAILED_STEP%"
call :cleanup
echo E2E_COMMERCE_UNBLOCK: FAIL at %FAILED_STEP%
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
set "REQ_FILE=%TEMP_DIR%\%SCRIPT_NAME%_req.json"
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

:expect_status
set "LABEL=%~1"
set "EXPECTED=%~2"
set "ALT=%~3"
if "!LAST_STATUS!"=="%EXPECTED%" exit /b 0
if not "%ALT%"=="" if "!LAST_STATUS!"=="%ALT%" exit /b 0
call :log "[FAIL] %LABEL% expected %EXPECTED% got !LAST_STATUS!"
exit /b 1

:extract_json_field
set "FILE=%~1"
set "FIELD=%~2"
set "OUTVAR=%~3"
for /f "usebackq delims=" %%v in (`python -c "import json; data=json.load(open(r'%FILE%')); path=r'%FIELD%'.split('.'); cur=data;\nfor part in path:\n  if not part:\n    continue\n  if isinstance(cur, dict):\n    cur=cur.get(part)\n  else:\n    cur=None\n    break\nprint('' if cur is None else cur)"`) do set "%OUTVAR%=%%v"
exit /b 0
