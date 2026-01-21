@echo off
rem Preconditions (env vars):
rem   BASE_URL (default http://localhost)
rem   CORE_ADMIN_URL (default %BASE_URL%/api/core/v1/admin)
rem   CORE_PORTAL_URL (default %BASE_URL%/api/core/portal)
rem   AUTH_URL (default %BASE_URL%/api/auth)
rem   ADMIN_TOKEN (Bearer admin token)
rem   CLIENT_EMAIL, CLIENT_PASSWORD (client portal credentials)
rem Optional:
rem   CLIENT_TOKEN (skip login if set)
rem   ORG_ID (fallback from /portal/me if not set)
rem   PLAN_CODE (default CONTROL)
rem   PLAN_VERSION (default 1)
setlocal enabledelayedexpansion

set "SCRIPT_NAME=smoke_portal_unification_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%BASE_URL%/api/core/v1/admin"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%BASE_URL%/api/core/portal"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%PLAN_CODE%"=="" set "PLAN_CODE=CONTROL"
if "%PLAN_VERSION%"=="" set "PLAN_VERSION=1"
set "ENTITLEMENTS_PAYLOAD={""reason"":""smoke_e2e""}"

if not exist logs mkdir logs
set "LOG_DATE=%DATE:/=-%"
set "LOG_DATE=%LOG_DATE: =_%"
set "LOG_FILE=logs\%SCRIPT_NAME%_%LOG_DATE%.log"

call :log "Starting %SCRIPT_NAME%"
call :log "BASE_URL=%BASE_URL%"
call :log "CORE_ADMIN_URL=%CORE_ADMIN_URL%"
call :log "CORE_PORTAL_URL=%CORE_PORTAL_URL%"
call :log "AUTH_URL=%AUTH_URL%"

if "%ADMIN_TOKEN%"=="" (
  call :fail "precheck_missing_ADMIN_TOKEN"
)
if "%CLIENT_TOKEN%"=="" (
  if "%CLIENT_EMAIL%"=="" call :fail "precheck_missing_CLIENT_EMAIL"
  if "%CLIENT_PASSWORD%"=="" call :fail "precheck_missing_CLIENT_PASSWORD"
)

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "STEP=0_health"
call :log "[%STEP%] GET %BASE_URL%/api/core/health"
set "HTTP_HEADER="
call :http_get "%BASE_URL%/api/core/health" "%TEMP%\portal_health.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_health.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_health.json" "\"status\":\"ok\"" || call :fail "%STEP%"

set "STEP=1_client_login"
if "%CLIENT_TOKEN%"=="" (
  call :log "[%STEP%] POST %AUTH_URL%/login"
  set "LOGIN_PAYLOAD={""email"":""%CLIENT_EMAIL%"",""password"":""%CLIENT_PASSWORD%""}"
  call :http_post "%AUTH_URL%/login" "!LOGIN_PAYLOAD!" "%TEMP%\client_login.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\client_login.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  call :extract_json_field "%TEMP%\client_login.json" "access_token" CLIENT_TOKEN
  if "!CLIENT_TOKEN!"=="" call :fail "%STEP%"
)

set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

call :log "[%STEP%] GET %CORE_PORTAL_URL%/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_me.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me.json" "\"org\"" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me.json" "\"org_id\"" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me.json" "\"roles\"" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me.json" "\"capabilities\"" || call :fail "%STEP%"

set "HAS_CLIENT_ROLE=0"
set "HAS_PARTNER_ROLE=0"
findstr /c:"CLIENT" "%TEMP%\portal_me.json" >nul && set "HAS_CLIENT_ROLE=1"
findstr /c:"PARTNER" "%TEMP%\portal_me.json" >nul && set "HAS_PARTNER_ROLE=1"
if "!HAS_CLIENT_ROLE!!HAS_PARTNER_ROLE!"=="00" call :fail "%STEP%"

if "%ORG_ID%"=="" (
  call :extract_json_field "%TEMP%\portal_me.json" "org_id" ORG_ID
)
if "!ORG_ID!"=="" call :fail "%STEP%"
call :log "ORG_ID=!ORG_ID!"

set "STEP=2_client_to_partner"
if "!HAS_PARTNER_ROLE!"=="0" (
  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/add"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  set "ROLE_PAYLOAD={""role"":""PARTNER"",""reason"":""smoke_e2e_client_to_partner""}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/add" "!ROLE_PAYLOAD!" "%TEMP%\add_partner_role.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\add_partner_role.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
  set "ADDED_PARTNER_ROLE=1"
) else (
  call :log "[%STEP%] Partner role already present, skipping add"
)

set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me_partner.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_me_partner.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_partner.json" "PARTNER" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_partner.json" "PARTNER_CORE" || call :fail "%STEP%"

call :log "[%STEP%] GET %BASE_URL%/api/core/partner/me"
call :http_get "%BASE_URL%/api/core/partner/me" "%TEMP%\partner_me.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_me.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=3_partner_to_client"
if "!HAS_CLIENT_ROLE!"=="0" (
  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/add"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  set "ROLE_PAYLOAD={""role"":""CLIENT"",""reason"":""smoke_e2e_partner_to_client""}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/add" "!ROLE_PAYLOAD!" "%TEMP%\add_client_role.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\add_client_role.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
) else (
  call :log "[%STEP%] Client role already present, skipping role add/plan update"
)

if "!HAS_CLIENT_ROLE!"=="0" (
  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/plan"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  set "PLAN_PAYLOAD={""plan_code"":""%PLAN_CODE%"",""plan_version"":%PLAN_VERSION%,""billing_cycle"":""MONTHLY"",""status"":""ACTIVE"",""reason"":""smoke_e2e_partner_to_client""}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/plan" "!PLAN_PAYLOAD!" "%TEMP%\plan_update.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\plan_update.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

  call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute" "!ENTITLEMENTS_PAYLOAD!" "%TEMP%\entitlements_recompute.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\entitlements_recompute.json"
  if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
)

set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%CORE_PORTAL_URL%/me" "%TEMP%\portal_me_client.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\portal_me_client.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_client.json" "CLIENT_CORE" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_client.json" "\"subscription\"" || call :fail "%STEP%"
call :expect_contains "%TEMP%\portal_me_client.json" "ACTIVE" || call :fail "%STEP%"

set "STEP=4_billing_overdue"
call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/status"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "STATUS_PAYLOAD={""status"":""OVERDUE"",""reason"":""smoke_e2e_overdue""}"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/status" "!STATUS_PAYLOAD!" "%TEMP%\status_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\status_overdue.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

call :log "[%STEP%] POST %CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute" "!ENTITLEMENTS_PAYLOAD!" "%TEMP%\entitlements_recompute_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\entitlements_recompute_overdue.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

call :log "[%STEP%] POST %BASE_URL%/api/core/client/exports/jobs"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
set "CLIENT_WRITE_PAYLOAD={""report_type"":""CARDS"",""format"":""CSV"",""filters"":{}}"
call :http_post "%BASE_URL%/api/core/client/exports/jobs" "!CLIENT_WRITE_PAYLOAD!" "%TEMP%\client_write.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\client_write.json"
if not "!LAST_STATUS!"=="403" call :fail "%STEP%"
call :expect_contains_any "%TEMP%\client_write.json" "billing_soft_blocked" "subscription_overdue" || call :fail "%STEP%"

call :log "[%STEP%] GET %BASE_URL%/api/core/partner/me"
set "HTTP_HEADER=%CLIENT_AUTH_HEADER%"
call :http_get "%BASE_URL%/api/core/partner/me" "%TEMP%\partner_me_overdue.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\partner_me_overdue.json"
if not "!LAST_STATUS!"=="200" call :fail "%STEP%"

set "STEP=5_cleanup"
call :cleanup

call :log "E2E_PORTAL_UNIFICATION: PASS"
echo E2E_PORTAL_UNIFICATION: PASS
exit /b 0

:cleanup
if "!ORG_ID!"=="" exit /b 0
call :log "[%STEP%] Cleanup: set status ACTIVE"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
set "STATUS_PAYLOAD={""status"":""ACTIVE"",""reason"":""smoke_e2e_cleanup""}"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/status" "!STATUS_PAYLOAD!" "%TEMP%\status_active.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\status_active.json"

call :log "[%STEP%] Cleanup: recompute entitlements"
set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/entitlements/recompute" "!ENTITLEMENTS_PAYLOAD!" "%TEMP%\entitlements_recompute_cleanup.json"
call :log "Status: !LAST_STATUS!"
call :append_response "%TEMP%\entitlements_recompute_cleanup.json"

if "!ADDED_PARTNER_ROLE!"=="1" (
  call :log "[%STEP%] Cleanup: remove PARTNER role"
  set "HTTP_HEADER=%ADMIN_AUTH_HEADER%"
  set "ROLE_PAYLOAD={""role"":""PARTNER"",""reason"":""smoke_e2e_cleanup""}"
  call :http_post "%CORE_ADMIN_URL%/commercial/orgs/!ORG_ID!/roles/remove" "!ROLE_PAYLOAD!" "%TEMP%\remove_partner_role.json"
  call :log "Status: !LAST_STATUS!"
  call :append_response "%TEMP%\remove_partner_role.json"
)
exit /b 0

:fail
set "FAILED_STEP=%~1"
call :log "E2E_PORTAL_UNIFICATION: FAIL at %FAILED_STEP%"
call :cleanup
echo E2E_PORTAL_UNIFICATION: FAIL at %FAILED_STEP%
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

:expect_contains_any
set "FILE=%~1"
set "SUB_A=%~2"
set "SUB_B=%~3"
findstr /c:"%SUB_A%" "%FILE%" >nul && exit /b 0
findstr /c:"%SUB_B%" "%FILE%" >nul && exit /b 0
exit /b 1

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
