@echo off
rem Preconditions (env vars):
rem   BASE_URL (default http://localhost)
rem   CORE_PARTNER_URL (default %BASE_URL%/api/core/partner)
rem   CORE_CLIENT_URL (default %BASE_URL%/api/core/client)
rem   CORE_ADMIN_URL (default %BASE_URL%/api/core/v1/admin)
rem   AUTH_URL (default %BASE_URL%/api/auth)
rem   ADMIN_TOKEN (Bearer admin token)
rem   PARTNER_EMAIL, PARTNER_PASSWORD
rem   CLIENT_EMAIL, CLIENT_PASSWORD
rem Optional:
rem   PARTNER_TOKEN, CLIENT_TOKEN
rem   PAYOUT_BATCH_ID (optional trace validation)
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_partner_trust_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%BASE_URL%/api/core/partner"
if "%CORE_CLIENT_URL%"=="" set "CORE_CLIENT_URL=%BASE_URL%/api/core/client"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/v1/admin"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/auth"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "BASE_URL=%BASE_URL%"
call :log "CORE_PARTNER_URL=%CORE_PARTNER_URL%"
call :log "CORE_CLIENT_URL=%CORE_CLIENT_URL%"
call :log "CORE_ADMIN_URL=%CORE_ADMIN_URL%"
call :log "AUTH_URL=%AUTH_URL%"

if "%ADMIN_TOKEN%"=="" call :fail "precheck_missing_ADMIN_TOKEN"
if "%PARTNER_TOKEN%"=="" (
  if "%PARTNER_EMAIL%"=="" call :fail "precheck_missing_PARTNER_EMAIL"
  if "%PARTNER_PASSWORD%"=="" call :fail "precheck_missing_PARTNER_PASSWORD"
)
if "%CLIENT_TOKEN%"=="" (
  if "%CLIENT_EMAIL%"=="" call :fail "precheck_missing_CLIENT_EMAIL"
  if "%CLIENT_PASSWORD%"=="" call :fail "precheck_missing_CLIENT_PASSWORD"
)

set "STEP=1_partner_login"
if "%PARTNER_TOKEN%"=="" (
  set "LOGIN_PAYLOAD={""email"":""%PARTNER_EMAIL%"",""password"":""%PARTNER_PASSWORD%""}"
  call :log "[%STEP%] POST %AUTH_URL%/login"
  call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\partner_login.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\partner_login.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  call :extract_json_field "%TEMP%\partner_login.json" "access_token" PARTNER_TOKEN
  if "!PARTNER_TOKEN!"=="" call :fail "%STEP%"
)

set "STEP=2_client_login"
if "%CLIENT_TOKEN%"=="" (
  set "LOGIN_PAYLOAD={""email"":""%CLIENT_EMAIL%"",""password"":""%CLIENT_PASSWORD%""}"
  call :log "[%STEP%] POST %AUTH_URL%/login"
  call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\client_login.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\client_login.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  call :extract_json_field "%TEMP%\client_login.json" "access_token" CLIENT_TOKEN
  if "!CLIENT_TOKEN!"=="" call :fail "%STEP%"
)

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=3_create_product"
set "PRODUCT_TITLE=Smoke Trust Product %RANDOM%"
set "PRODUCT_PAYLOAD={""type"":""SERVICE"",""title"":""!PRODUCT_TITLE!"",""description"":""Smoke trust product"",""category"":""services"",""price_model"":""FIXED"",""price_config"":{""amount"":1000,""currency"":""RUB""}}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/products"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/products" "!PRODUCT_PAYLOAD!" "%TEMP%\product_create.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\product_create.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :extract_json_field "%TEMP%\product_create.json" "id" PRODUCT_ID
if "!PRODUCT_ID!"=="" call :fail "%STEP%"

set "STEP=4_publish_product"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/products/!PRODUCT_ID!/publish"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/products/!PRODUCT_ID!/publish" "{}" "%TEMP%\product_publish.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\product_publish.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=5_create_order"
set "ORDER_PAYLOAD={""product_id"":""!PRODUCT_ID!"",""quantity"":1}"
call :log "[%STEP%] POST %CORE_CLIENT_URL%/marketplace/orders"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_post "%CORE_CLIENT_URL%/marketplace/orders" "!ORDER_PAYLOAD!" "%TEMP%\order_create.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_create.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :extract_json_field "%TEMP%\order_create.json" "id" ORDER_ID
if "!ORDER_ID!"=="" call :fail "%STEP%"

set "STEP=6_accept_order"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/!ORDER_ID!/accept"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/orders/!ORDER_ID!/accept" "{}" "%TEMP%\order_accept.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_accept.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=7_complete_order"
set "COMPLETE_PAYLOAD={""summary"":""Smoke completed""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/!ORDER_ID!/complete"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/orders/!ORDER_ID!/complete" "!COMPLETE_PAYLOAD!" "%TEMP%\order_complete.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_complete.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=8_admin_snapshot"
call :log "[%STEP%] GET %CORE_ADMIN_URL%/marketplace/orders/!ORDER_ID!/settlement-snapshot"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_get "%CORE_ADMIN_URL%/marketplace/orders/!ORDER_ID!/settlement-snapshot" "%TEMP%\order_snapshot.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_snapshot.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "(Get-Content '%TEMP%\\order_snapshot.json' | ConvertFrom-Json).gross_amount"`) do set "GROSS_AMOUNT=%%d"
for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "(Get-Content '%TEMP%\\order_snapshot.json' | ConvertFrom-Json).platform_fee"`) do set "PLATFORM_FEE=%%d"
for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "(Get-Content '%TEMP%\\order_snapshot.json' | ConvertFrom-Json).penalties"`) do set "PENALTIES=%%d"
for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "(Get-Content '%TEMP%\\order_snapshot.json' | ConvertFrom-Json).partner_net"`) do set "PARTNER_NET=%%d"
for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "(Get-Content '%TEMP%\\order_snapshot.json' | ConvertFrom-Json).currency"`) do set "CURRENCY=%%d"

set "STEP=9_admin_finalize"
set "OVERRIDE_PAYLOAD={""gross_amount"":!GROSS_AMOUNT!,""platform_fee"":!PLATFORM_FEE!,""penalties"":!PENALTIES!,""partner_net"":!PARTNER_NET!,""currency"":""!CURRENCY!"",""reason"":""smoke trust finalize""}"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/marketplace/orders/!ORDER_ID!/settlement-override"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_ADMIN_URL%/marketplace/orders/!ORDER_ID!/settlement-override" "!OVERRIDE_PAYLOAD!" "%TEMP%\order_override.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_override.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=10_settlement_breakdown"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/orders/!ORDER_ID!/settlement"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/orders/!ORDER_ID!/settlement" "%TEMP%\order_settlement.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_settlement.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\order_settlement.json" "gross_amount" || call :fail "%STEP%"
call :expect_contains "%TEMP%\order_settlement.json" "hash" || call :fail "%STEP%"

set "STEP=11_ledger_list"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/ledger"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/ledger?limit=50" "%TEMP%\partner_ledger.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_ledger.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "$items = (Get-Content '%TEMP%\\partner_ledger.json' | ConvertFrom-Json).items; ($items | Where-Object { $_.order_id -eq '%ORDER_ID%' } | Select-Object -First 1).id"`) do set "LEDGER_ENTRY_ID=%%d"
if "!LEDGER_ENTRY_ID!"=="" call :fail "%STEP%"

set "STEP=12_ledger_explain"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/ledger/!LEDGER_ENTRY_ID!/explain"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/ledger/!LEDGER_ENTRY_ID!/explain" "%TEMP%\ledger_explain.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\ledger_explain.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\ledger_explain.json" "amount" || call :fail "%STEP%"

for /f "usebackq tokens=*" %%d in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"`) do set "TODAY=%%d"

set "STEP=13_export_chain"
set "EXPORT_PAYLOAD={""from"":""!TODAY!"",""to"":""!TODAY!"",""format"":""CSV""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/exports/settlement-chain"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/exports/settlement-chain" "!EXPORT_PAYLOAD!" "%TEMP%\export_job.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\export_job.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :expect_contains "%TEMP%\export_job.json" "\"id\"" || call :fail "%STEP%"

if not "%PAYOUT_BATCH_ID%"=="" (
  set "STEP=14_payout_trace"
  call :log "[%STEP%] GET %CORE_PARTNER_URL%/payouts/%PAYOUT_BATCH_ID%/trace"
  set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
  call :http_get "%CORE_PARTNER_URL%/payouts/%PAYOUT_BATCH_ID%/trace" "%TEMP%\payout_trace.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\payout_trace.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
)

call :log "E2E_PARTNER_TRUST: PASS"
echo E2E_PARTNER_TRUST: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_PARTNER_TRUST: FAIL at %FAILED_STEP%"
echo E2E_PARTNER_TRUST: FAIL at %FAILED_STEP%
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
set "REQ_FILE=%TEMP%\%SCRIPT_NAME%_req.json"
> "!REQ_FILE!" echo(!BODY!
if "!HTTP_HEADER!"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X POST -H "Content-Type: application/json" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X POST -H "Content-Type: application/json" -H "!HTTP_HEADER!" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
)
exit /b 0

:expect_contains
set "FILE=%~1"
set "NEEDLE=%~2"
findstr /c:%NEEDLE% "%FILE%" >NUL
exit /b %ERRORLEVEL%

:extract_json_field
set "JSON_FILE=%~1"
set "JSON_FIELD=%~2"
set "OUT_VAR=%~3"
for /f "usebackq tokens=1,* delims=:" %%a in (`findstr /r /c:"\"%JSON_FIELD%\"" "%JSON_FILE%"`) do (
  set "RAW=%%b"
)
set "RAW=%RAW:,=%"
set "RAW=%RAW:}=%"
set "RAW=%RAW:\"=%"
set "RAW=%RAW: =%"
set "%OUT_VAR%=%RAW%"
exit /b 0
