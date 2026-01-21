@echo off
rem Preconditions (env vars):
rem   BASE_URL (default http://localhost)
rem   CORE_ADMIN_URL (default %BASE_URL%/api/core/v1/admin)
rem   CORE_PARTNER_URL (default %BASE_URL%/api/core/partner)
rem   CORE_PORTAL_URL (default %BASE_URL%/api/core/portal)
rem   AUTH_URL (default %BASE_URL%/api/auth)
rem   ADMIN_TOKEN (Bearer admin token)
rem   CLIENT_EMAIL, CLIENT_PASSWORD (portal credentials)
rem Optional:
rem   PARTNER_TOKEN (skip login if set)
rem   ORG_ID (fallback from /portal/me if not set)
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_partner_legal_payout_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/v1/admin"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%BASE_URL%/api/core/partner"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "BASE_URL=%BASE_URL%"
call :log "CORE_ADMIN_URL=%CORE_ADMIN_URL%"
call :log "CORE_PARTNER_URL=%CORE_PARTNER_URL%"
call :log "CORE_PORTAL_URL=%CORE_PORTAL_URL%"
call :log "AUTH_URL=%AUTH_URL%"

if "%ADMIN_TOKEN%"=="" call :fail "precheck_missing_ADMIN_TOKEN"
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
if "%ORG_ID%"=="" call :extract_json_field "%TEMP%\portal_me.json" "org_id" ORG_ID
if "!ORG_ID!"=="" call :fail "%STEP%"
call :log "ORG_ID=!ORG_ID!"

set "STEP=3_create_offer"
set "OFFER_CODE=smoke-offer-%RANDOM%"
set "OFFER_TITLE=Smoke Offer %RANDOM%"
set "OFFER_PAYLOAD={""code"":""!OFFER_CODE!"",""title"":""!OFFER_TITLE!"",""description"":""Smoke offer"",""base_price"":1000,""currency"":""RUB""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/offers"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/offers" "!OFFER_PAYLOAD!" "%TEMP%\offer_create.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\offer_create.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :extract_json_field "%TEMP%\offer_create.json" "id" OFFER_ID
if "!OFFER_ID!"=="" call :fail "%STEP%"

set "STEP=4_seed_order"
set "ORDER_PAYLOAD={""partner_org_id"":!ORG_ID!,""offer_id"":""!OFFER_ID!"",""title"":""Smoke order""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/seed"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/orders/seed" "!ORDER_PAYLOAD!" "%TEMP%\order_seed.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_seed.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"
call :extract_json_field "%TEMP%\order_seed.json" "id" ORDER_ID
if "!ORDER_ID!"=="" call :fail "%STEP%"

set "STEP=5_accept_order"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/!ORDER_ID!/accept"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/orders/!ORDER_ID!/accept" "{}" "%TEMP%\order_accept.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_accept.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=6_complete_order"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/orders/!ORDER_ID!/status"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
set "STATUS_PAYLOAD={""status"":""DONE""}"
call :http_post "%CORE_PARTNER_URL%/orders/!ORDER_ID!/status" "!STATUS_PAYLOAD!" "%TEMP%\order_done.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\order_done.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=7_payout_blocked"
set "PAYOUT_PAYLOAD={""amount"":1000,""currency"":""RUB""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/request (expect 403)"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/payouts/request" "!PAYOUT_PAYLOAD!" "%TEMP%\payout_request_blocked.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\payout_request_blocked.json"
if not "!LAST_STATUS!"=="403" call :fail "%STEP%"

set "STEP=8_fill_legal_profile"
set "LEGAL_PROFILE_PAYLOAD={""legal_type"":""IP"",""country"":""RU"",""tax_residency"":""RU"",""tax_regime"":""USN"",""vat_applicable"":false,""vat_rate"":0}"
call :log "[%STEP%] PUT %CORE_PARTNER_URL%/legal/profile"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_put "%CORE_PARTNER_URL%/legal/profile" "!LEGAL_PROFILE_PAYLOAD!" "%TEMP%\legal_profile.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\legal_profile.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=9_fill_legal_details"
set "LEGAL_DETAILS_PAYLOAD={""legal_name"":""Smoke Partner"",""inn"":""1234567890"",""kpp"":""123456789"",""ogrn"":""1234567890123"",""bank_account"":""40702810900000000001"",""bank_bic"":""044525000"",""bank_name"":""NEFT Bank""}"
call :log "[%STEP%] PUT %CORE_PARTNER_URL%/legal/details"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_put "%CORE_PARTNER_URL%/legal/details" "!LEGAL_DETAILS_PAYLOAD!" "%TEMP%\legal_details.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\legal_details.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=10_admin_verify"
set "VERIFY_PAYLOAD={""status"":""VERIFIED"",""comment"":""smoke verified""}"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/partners/!ORG_ID!/legal-profile/status"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_ADMIN_URL%/partners/!ORG_ID!/legal-profile/status" "!VERIFY_PAYLOAD!" "%TEMP%\legal_verify.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\legal_verify.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=11_payout_allowed"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/request (expect 201)"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_post "%CORE_PARTNER_URL%/payouts/request" "!PAYOUT_PAYLOAD!" "%TEMP%\payout_request_allowed.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\payout_request_allowed.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"

set "STEP=12_generate_pack"
set "PACK_PAYLOAD={""format"":""ZIP""}"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/partners/!ORG_ID!/legal-pack"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_ADMIN_URL%/partners/!ORG_ID!/legal-pack" "!PACK_PAYLOAD!" "%TEMP%\legal_pack.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\legal_pack.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

call :log "E2E_PARTNER_LEGAL_PAYOUT: PASS"
echo E2E_PARTNER_LEGAL_PAYOUT: PASS
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_PARTNER_LEGAL_PAYOUT: FAIL at %FAILED_STEP%"
echo E2E_PARTNER_LEGAL_PAYOUT: FAIL at %FAILED_STEP%
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

:http_put
set "URL=%~1"
set "BODY=%~2"
set "OUT=%~3"
set "REQ_FILE=%TEMP%\%SCRIPT_NAME%_req.json"
> "!REQ_FILE!" echo(!BODY!
if "!HTTP_HEADER!"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X PUT -H "Content-Type: application/json" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X PUT -H "Content-Type: application/json" -H "!HTTP_HEADER!" --data-binary @"!REQ_FILE!" "%URL%"`) do set "LAST_STATUS=%%c"
)
exit /b 0

:extract_json_field
set "JSON_FILE=%~1"
set "JSON_FIELD=%~2"
set "OUT_VAR=%~3"
for /f "usebackq tokens=2 delims=:" %%a in (`findstr /c:"\"%JSON_FIELD%\"" "%JSON_FILE%"`) do (
  set "VALUE=%%~a"
  set "VALUE=!VALUE:,=!"
  set "VALUE=!VALUE:"=!"
  set "VALUE=!VALUE: =!"
  set "%OUT_VAR%=!VALUE!"
  exit /b 0
)
set "%OUT_VAR%="
exit /b 0

:expect_contains
set "FILE=%~1"
set "TEXT=%~2"
findstr /c:%TEXT% "%FILE%" >nul
exit /b %ERRORLEVEL%
