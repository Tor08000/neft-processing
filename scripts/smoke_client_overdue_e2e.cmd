@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_client_overdue_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_CLIENT_URL%"=="" set "CORE_CLIENT_URL=%BASE_URL%/api/core/client"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%CORE_ADMIN_FINANCE_URL%"=="" set "CORE_ADMIN_FINANCE_URL=%BASE_URL%/api/core/admin/finance"
if "%CORE_ADMIN_V1_URL%"=="" set "CORE_ADMIN_V1_URL=%BASE_URL%/api/core/v1/admin"

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
set "LOG_FILE=%LOG_DIR%\%SCRIPT_NAME%_%RUN_TS%.log"

set "TEMP_DIR=%TEMP%\%SCRIPT_NAME%_%RUN_TS%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=1_client_login"
if "%CLIENT_TOKEN%"=="" (
  call :log "[%STEP%] POST %AUTH_URL%/login"
  set "LOGIN_PAYLOAD={""email"":""%CLIENT_EMAIL%"",""password"":""%CLIENT_PASSWORD%"",""portal"":""client""}"
  call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP_DIR%\client_login.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP_DIR%\client_login.json"
  call :expect_status "%STEP%" "200" || call :fail "%STEP%"
  call :extract_json_field "%TEMP_DIR%\client_login.json" "access_token" CLIENT_TOKEN
  if "!CLIENT_TOKEN!"=="" call :fail "%STEP%"
)

set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

set "STEP=2_portal_me"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP_DIR%\portal_me.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\portal_me.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\portal_me.json" "org_id" ORG_ID
if "!ORG_ID!"=="" call :fail "%STEP%"

set "STEP=3_generate_invoice"
call :log "[%STEP%] POST %CORE_ADMIN_V1_URL%/billing/generate"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "GENERATE_PAYLOAD={""org_id"":!ORG_ID!}"
call :http_post "%CORE_ADMIN_V1_URL%/billing/generate" "!GENERATE_PAYLOAD!" "%TEMP_DIR%\invoice_generate.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\invoice_generate.json"

set "STEP=4_list_invoices"
call :log "[%STEP%] GET %CORE_CLIENT_URL%/invoices"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_CLIENT_URL%/invoices" "%TEMP_DIR%\invoices_list.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\invoices_list.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
for /f "usebackq delims=" %%i in (`python -c "import json; d=json.load(open(r'%TEMP_DIR%\\invoices_list.json')); items=d.get('items') or []; print(items[0].get('id') if items else '')"`) do set "INVOICE_ID=%%i"
if "!INVOICE_ID!"=="" call :fail "%STEP%"

set "STEP=5_mark_overdue"
call :log "[%STEP%] POST %CORE_ADMIN_FINANCE_URL%/invoices/!INVOICE_ID!/mark-overdue"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "MARK_PAYLOAD={""reason"":""smoke_overdue""}"
call :http_post "%CORE_ADMIN_FINANCE_URL%/invoices/!INVOICE_ID!/mark-overdue" "!MARK_PAYLOAD!" "%TEMP_DIR%\invoice_mark_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\invoice_mark_overdue.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"

set "STEP=6_subscription_overdue"
call :log "[%STEP%] POST %CORE_ADMIN_V1_URL%/commercial/orgs/!ORG_ID!/status"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "STATUS_PAYLOAD={""status"":""OVERDUE"",""reason"":""smoke_overdue""}"
call :http_post "%CORE_ADMIN_V1_URL%/commercial/orgs/!ORG_ID!/status" "!STATUS_PAYLOAD!" "%TEMP_DIR%\status_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\status_overdue.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"

set "STEP=7_portal_overdue"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP_DIR%\portal_me_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\portal_me_overdue.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :expect_contains "%TEMP_DIR%\portal_me_overdue.json" "\"access_state\":\"OVERDUE\"" || call :fail "%STEP%"

set "STEP=8_invoice_detail"
call :log "[%STEP%] GET %CORE_CLIENT_URL%/invoices/!INVOICE_ID!"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_CLIENT_URL%/invoices/!INVOICE_ID!" "%TEMP_DIR%\invoice_detail.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\invoice_detail.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\invoice_detail.json" "amount_due" INVOICE_AMOUNT
if "!INVOICE_AMOUNT!"=="" call :extract_json_field "%TEMP_DIR%\invoice_detail.json" "total_amount" INVOICE_AMOUNT
if "!INVOICE_AMOUNT!"=="" call :fail "%STEP%"

set "STEP=9_payment_intake"
call :log "[%STEP%] POST %CORE_CLIENT_URL%/payments/intake"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
set "INTAKE_PAYLOAD={""invoice_id"":!INVOICE_ID!,""amount"":!INVOICE_AMOUNT!,""method"":""bank_transfer"",""reference"":""SMOKE-OVERDUE-1""}"
call :http_post "%CORE_CLIENT_URL%/payments/intake" "!INTAKE_PAYLOAD!" "%TEMP_DIR%\payment_intake.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\payment_intake.json"
call :expect_status "%STEP%" "201" "200" || call :fail "%STEP%"
call :extract_json_field "%TEMP_DIR%\payment_intake.json" "id" PAYMENT_INTAKE_ID
if "!PAYMENT_INTAKE_ID!"=="" call :fail "%STEP%"

set "STEP=10_admin_list_intakes"
call :log "[%STEP%] GET %CORE_ADMIN_FINANCE_URL%/payment-intakes"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_get "%CORE_ADMIN_FINANCE_URL%/payment-intakes" "%TEMP_DIR%\payment_intakes.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\payment_intakes.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :expect_contains "%TEMP_DIR%\payment_intakes.json" "\"id\":!PAYMENT_INTAKE_ID!" || call :fail "%STEP%"

set "STEP=11_admin_confirm"
call :log "[%STEP%] POST %CORE_ADMIN_FINANCE_URL%/payment-intakes/!PAYMENT_INTAKE_ID!/confirm"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "CONFIRM_PAYLOAD={""reason"":""smoke_confirm""}"
call :http_post "%CORE_ADMIN_FINANCE_URL%/payment-intakes/!PAYMENT_INTAKE_ID!/confirm" "!CONFIRM_PAYLOAD!" "%TEMP_DIR%\payment_confirm.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\payment_confirm.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"

set "STEP=12_portal_active"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP_DIR%\portal_me_active.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP_DIR%\portal_me_active.json"
call :expect_status "%STEP%" "200" || call :fail "%STEP%"
call :expect_contains "%TEMP_DIR%\portal_me_active.json" "\"access_state\":\"ACTIVE\"" || call :fail "%STEP%"

call :log "E2E_CLIENT_OVERDUE: PASS"
echo E2E_CLIENT_OVERDUE: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_CLIENT_OVERDUE: FAIL at %FAILED_STEP%"
echo E2E_CLIENT_OVERDUE: FAIL at %FAILED_STEP%
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
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X POST -H "Content-Type: application/json" -H "!HTTP_HEADER!" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
)
exit /b 0

:expect_status
set "STEP_NAME=%~1"
shift
set "EXPECTED=0"
:expect_status_loop
if "%~1"=="" goto :expect_status_done
if "%LAST_STATUS%"=="%~1" set "EXPECTED=1"
shift
goto :expect_status_loop
:expect_status_done
if "%EXPECTED%"=="1" exit /b 0
call :log "[%STEP_NAME%] Expected status %* but got %LAST_STATUS%"
exit /b 1

:expect_contains
set "FILE=%~1"
set "NEEDLE=%~2"
findstr /c:%NEEDLE% "%FILE%" >nul
if errorlevel 1 (
  call :log "Expected %NEEDLE% in %FILE%"
  exit /b 1
)
exit /b 0

:extract_json_field
set "FILE=%~1"
set "KEY=%~2"
set "VAR=%~3"
for /f "usebackq delims=" %%v in (`python -c "import json; import sys; data=json.load(open(r'%FILE%'));\nkeys='%KEY%'.split('.');\ncur=data\nfor k in keys:\n  if isinstance(cur, dict):\n    cur=cur.get(k)\n  else:\n    cur=None\n    break\nprint(cur if cur is not None else '')"`) do set "%VAR%=%%v"
exit /b 0
