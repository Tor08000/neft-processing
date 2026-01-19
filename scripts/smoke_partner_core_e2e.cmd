@echo off
rem Preconditions (env vars):
rem   BASE_URL (default http://localhost)
rem   CORE_ADMIN_URL (default %BASE_URL%/api/core/v1/admin)
rem   CORE_PORTAL_URL (default %BASE_URL%/api/core/portal)
rem   CORE_PARTNER_URL (default %BASE_URL%/api/core/partner)
rem   AUTH_URL (default %BASE_URL%/api/auth)
rem   ADMIN_TOKEN (Bearer admin token)
rem   CLIENT_EMAIL, CLIENT_PASSWORD (portal credentials)
rem Optional:
rem   PARTNER_TOKEN (skip login if set)
rem   ORG_ID (fallback from /portal/me if not set)
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_partner_core_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/v1/admin"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%BASE_URL%/api/core/partner"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/auth"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "BASE_URL=%BASE_URL%"
call :log "CORE_ADMIN_URL=%CORE_ADMIN_URL%"
call :log "CORE_PORTAL_URL=%CORE_PORTAL_URL%"
call :log "CORE_PARTNER_URL=%CORE_PARTNER_URL%"
call :log "AUTH_URL=%AUTH_URL%"

if "%ADMIN_TOKEN%"=="" (
  call :fail "precheck_missing_ADMIN_TOKEN"
)
if "%PARTNER_TOKEN%"=="" (
  if "%CLIENT_EMAIL%"=="" call :fail "precheck_missing_CLIENT_EMAIL"
  if "%CLIENT_PASSWORD%"=="" call :fail "precheck_missing_CLIENT_PASSWORD"
)

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=1_login"
if "%PARTNER_TOKEN%"=="" (
  call :log "[%STEP%] POST %AUTH_URL%/login"
  set "LOGIN_PAYLOAD={""email"":""%CLIENT_EMAIL%"",""password"":""%CLIENT_PASSWORD%""}"
  call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\partner_login.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\partner_login.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  call :extract_json_field "%TEMP%\partner_login.json" "access_token" PARTNER_TOKEN
  if "!PARTNER_TOKEN!"=="" call :fail "%STEP%"
)

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

set "STEP=2_portal_me"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_me.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me.json" "\"org\"" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me.json" "\"capabilities\"" || call :fail "%STEP%"

set "HAS_PARTNER_ROLE=0"
findstr /c:"PARTNER" "%TEMP%\portal_me.json" >nul && set "HAS_PARTNER_ROLE=1"
if "!HAS_PARTNER_ROLE!"=="0" (
  if "%ORG_ID%"=="" call :extract_json_field "%TEMP%\portal_me.json" "org_id" ORG_ID
  if "!ORG_ID!"=="" call :fail "%STEP%"
  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/add"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  set "ROLE_PAYLOAD={""role"":""PARTNER"",""reason"":""smoke_partner_core_e2e""}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/add" "!ROLE_PAYLOAD!" "%TEMP%\add_partner_role.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\add_partner_role.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
  call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me_partner.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\portal_me_partner.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  call :expect_contains "%TEMP%\portal_me_partner.json" "PARTNER_CORE" || call :fail "%STEP%"
  if "%ORG_ID%"=="" call :extract_json_field "%TEMP%\portal_me_partner.json" "org_id" ORG_ID
) 
if "!HAS_PARTNER_ROLE!"=="1" (
  call :expect_contains "%TEMP%\portal_me.json" "PARTNER_CORE" || call :fail "%STEP%"
)

if "%ORG_ID%"=="" (
  call :extract_json_field "%TEMP%\portal_me.json" "org_id" ORG_ID
)
if "!ORG_ID!"=="" call :fail "%STEP%"
call :log "ORG_ID=!ORG_ID!"

set "STEP=3_create_offer"
set "OFFER_CODE=smoke-offer-%RANDOM%"
set "OFFER_TITLE=Smoke Offer %RANDOM%"
set "OFFER_PAYLOAD={""code"":""!OFFER_CODE!"",""title"":""!OFFER_TITLE!"",""description"":""Smoke offer""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/offers"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/offers" "!OFFER_PAYLOAD!" "%TEMP%\offer_create.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\offer_create.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"

set "STEP=4_list_offers"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/offers"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/offers" "%TEMP%\offers_list.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\offers_list.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\offers_list.json" "!OFFER_CODE!" || call :fail "%STEP%"

set "STEP=5_seed_order"
set "ORDER_PAYLOAD={""partner_org_id"":!ORG_ID!,""title"":""Smoke inbound order""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/seed"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/orders/seed" "!ORDER_PAYLOAD!" "%TEMP%\order_seed.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_seed.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :extract_json_field "%TEMP%\order_seed.json" "id" ORDER_ID
if "!ORDER_ID!"=="" call :fail "%STEP%"

set "STEP=6_list_orders"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/orders"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/orders" "%TEMP%\orders_list.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\orders_list.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\orders_list.json" "\"status\":\"NEW\"" || call :fail "%STEP%"

set "STEP=7_accept_order"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/!ORDER_ID!/accept"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/orders/!ORDER_ID!/accept" "{}" "%TEMP%\order_accept.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_accept.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=8_order_detail"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/orders/!ORDER_ID!"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PARTNER_URL%/orders/!ORDER_ID!" "%TEMP%\order_detail.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_detail.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\order_detail.json" "\"status\":\"ACCEPTED\"" || call :fail "%STEP%"

call :log "E2E_PARTNER_CORE: PASS"
echo E2E_PARTNER_CORE: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_PARTNER_CORE: FAIL at %FAILED_STEP%"
echo E2E_PARTNER_CORE: FAIL at %FAILED_STEP%
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
if "!FOUND!"=="" exit /b 0
for /f "tokens=2 delims=:" %%v in ("!FOUND!") do set "VALUE=%%v"
set "VALUE=!VALUE: =!"
set "VALUE=!VALUE:\"=!"
set "VALUE=!VALUE:,=!"
set "%OUTVAR%=!VALUE!"
exit /b 0
