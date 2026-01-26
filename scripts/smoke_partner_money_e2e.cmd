@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%BASE_URL%/api/core/partner"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=partner"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "BASE_URL=%BASE_URL%"
call :log "CORE_PORTAL_URL=%CORE_PORTAL_URL%"
call :log "CORE_PARTNER_URL=%CORE_PARTNER_URL%"
call :log "AUTH_URL=%AUTH_URL%"

set "STEP=1_login"
call :log "[%STEP%] POST %AUTH_URL%/login"
set "LOGIN_PAYLOAD={""email"":""%PARTNER_EMAIL%"",""password"":""%PARTNER_PASSWORD%""}"
call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\partner_login.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_login.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :extract_json_field "%TEMP%\partner_login.json" "access_token" PARTNER_TOKEN
if "!PARTNER_TOKEN!"=="" call :fail "%STEP%"

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

set "STEP=2_portal_me"
call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me_partner.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_me_partner.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_partner.json" "\"partner\"" || call :fail "%STEP%"

set "STEP=3_partner_dashboard"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/dashboard"
call :http_get "%CORE_PARTNER_URL%/dashboard" "%TEMP%\partner_dashboard.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_dashboard.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=4_partner_ledger"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/ledger"
call :http_get "%CORE_PARTNER_URL%/ledger?limit=5" "%TEMP%\partner_ledger.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_ledger.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=5_payout_preview"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/payouts/preview"
call :http_get "%CORE_PARTNER_URL%/payouts/preview" "%TEMP%\partner_payout_preview.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_payout_preview.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=6_payout_request"
set "PAYOUT_PAYLOAD={""amount"":1000,""currency"":""RUB""}"
call :log "[%STEP%] POST %CORE_PARTNER_URL%/payouts/request"
call :http_post "%CORE_PARTNER_URL%/payouts/request" "!PAYOUT_PAYLOAD!" "%TEMP%\partner_payout_request.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_payout_request.json"
if not "!LAST_STATUS!"=="201" call :fail "%STEP%"

set "STEP=7_payout_history"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/payouts/history"
call :http_get "%CORE_PARTNER_URL%/payouts/history" "%TEMP%\partner_payout_history.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_payout_history.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\partner_payout_history.json" "\"status\"" || call :fail "%STEP%"

set "STEP=8_partner_docs"
call :log "[%STEP%] GET %CORE_PARTNER_URL%/docs"
call :http_get "%CORE_PARTNER_URL%/docs" "%TEMP%\partner_docs.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_docs.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\\partner_docs.json')); items=data.get('items') or []; print(items[0].get('download_url','') if items else '')"`) do set "DOC_URL=%%t"
if "!DOC_URL!"=="" call :fail "%STEP%"
set "FULL_DOC_URL=!DOC_URL!"
if "!DOC_URL:~0,4!"=="/api" set "FULL_DOC_URL=%BASE_URL%!DOC_URL!"
call :log "[%STEP%] GET !FULL_DOC_URL!"
set "HTTP_HEADER=%PARTNER_AUTH_HEADER%"
call :http_get "!FULL_DOC_URL!" "%TEMP%\partner_doc_download.txt"
call :log "Status: !LAST_STATUS!"
if not "!LAST_STATUS!"=="302" if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

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
