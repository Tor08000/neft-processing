@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get LocalDateTime /value') do set "dt=%%I"
set "ts=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,4%"
set "LOG_FILE=%LOG_DIR%\\smoke_admin_explain_%ts%.log"

echo smoke_admin_explain_e2e.cmd started at %date% %time% > "%LOG_FILE%"

call :log "[1/10] admin head check"
call :head_check "%GATEWAY_BASE%/admin/" "200 301 302"
if errorlevel 1 goto fail
call :head_check "%GATEWAY_BASE%/admin/assets/" "200 301 302"
if errorlevel 1 goto fail

call :log "[2/10] admin token"
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 goto fail
if "%TOKEN%"=="" goto fail
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :log "[3/10] admin me"
call :curl_check "%CORE_URL%/v1/admin/me" "admin_me.json" "200"
if errorlevel 1 goto fail

call :log "[4/10] runtime summary"
call :curl_check "%CORE_URL%/v1/admin/runtime/summary" "admin_runtime.json" "200"
if errorlevel 1 goto fail

call :log "[5/10] finance payouts"
call :curl_check "%CORE_URL%/admin/finance/payouts" "finance_payouts.json" "200"
if errorlevel 1 goto fail

for /f "usebackq delims=" %%P in (`python -c "import json; data=json.load(open('finance_payouts.json')); items=data.get('items') or data.get('payouts') or []; print((items[0].get('payout_id') if items else '') or '')"`) do set "PAYOUT_ID=%%P"
if "%PAYOUT_ID%"=="" goto fail

call :log "[6/10] payout detail"
call :curl_check "%CORE_URL%/admin/finance/payouts/%PAYOUT_ID%" "finance_payout_detail.json" "200"
if errorlevel 1 goto fail

for /f "usebackq delims=" %%P in (`python -c "import json; data=json.load(open('finance_payout_detail.json')); print(data.get('partner_id') or '')"`) do set "PARTNER_ID=%%P"
if "%PARTNER_ID%"=="" goto fail

call :log "[7/10] partner ledger + settlement"
call :curl_check "%CORE_URL%/admin/finance/partners/%PARTNER_ID%/ledger" "partner_ledger.json" "200"
if errorlevel 1 goto fail
call :curl_check "%CORE_URL%/admin/finance/partners/%PARTNER_ID%/settlement" "partner_settlement.json" "200"
if errorlevel 1 goto fail

call :log "[8/10] approve without settlement (expect 200/409)"
for /f "usebackq delims=" %%C in (`python -c "import uuid; print(uuid.uuid4())"`) do set "CORR_ID=%%C"
call :curl_check "%CORE_URL%/admin/finance/payouts/%PAYOUT_ID%/approve" "payout_approve.json" "200 409" "{\"reason\":\"smoke check\",\"correlation_id\":\"%CORR_ID%\"}"
if errorlevel 1 goto fail

call :log "[9/10] legal update without reason (expect 400/422)"
call :curl_check "%CORE_URL%/admin/legal/partners/%PARTNER_ID%/status" "legal_status.json" "400 422" "{\"status\":\"PENDING_REVIEW\"}"
if errorlevel 1 goto fail

call :log "[10/10] audit feed"
call :curl_check "%CORE_URL%/admin/audit" "audit_feed.json" "200"
if errorlevel 1 goto fail

echo PASS >> "%LOG_FILE%"
echo PASS
exit /b 0

:fail
echo FAIL >> "%LOG_FILE%"
echo FAIL
exit /b 1

:curl_check
set "URL=%~1"
set "OUT=%~2"
set "ALLOWED=%~3"
set "BODY=%~4"
set "CODE="

if "%BODY%"=="" (
  curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\\admin_explain_status.code" 2>> "%LOG_FILE%"
) else (
  curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "%BODY%" > "%TEMP%\\admin_explain_status.code" 2>> "%LOG_FILE%"
)
set /p CODE=<"%TEMP%\\admin_explain_status.code"
echo %ALLOWED% | findstr /C:"%CODE%" >nul
if errorlevel 1 exit /b 1
exit /b 0

:head_check
set "URL=%~1"
set "ALLOWED=%~2"
set "CODE="
curl -s -I -o NUL -w "%%{http_code}" "%URL%" > "%TEMP%\\admin_head_status.code" 2>> "%LOG_FILE%"
set /p CODE=<"%TEMP%\\admin_head_status.code"
echo %ALLOWED% | findstr /C:"%CODE%" >nul
if errorlevel 1 exit /b 1
exit /b 0

:log
>> "%LOG_FILE%" echo %~1
exit /b 0
