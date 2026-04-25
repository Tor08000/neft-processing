@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"

set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"

for /f "usebackq delims=" %%I in (`python -c "from datetime import datetime; print(datetime.now().strftime('%%Y-%%m-%%d_%%H%%M'))"`) do set "ts=%%I"
set "LOG_FILE=%LOG_DIR%\\smoke_admin_explain_%ts%.log"

echo smoke_admin_explain_e2e.cmd started at %date% %time% > "%LOG_FILE%"

call :log "[1/10] admin head check"
set "CODE="
curl -s -I -o NUL -w "%%{http_code}" "%GATEWAY_BASE%/admin/" > "%TEMP%\\admin_head_status.code" 2>> "%LOG_FILE%"
set /p CODE=<"%TEMP%\\admin_head_status.code"
echo 200 301 302 | findstr /C:"%CODE%" >nul
if errorlevel 1 goto fail
call scripts\smoke_gateway_assets.cmd >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto fail

call :log "[2/10] admin token"
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 goto fail
if "%TOKEN%"=="" goto fail
set "ADMIN_AUTH_HEADER=Authorization: Bearer %TOKEN%"
set "AUTH_HEADER=%ADMIN_AUTH_HEADER%"

call :log "[2.1/10] seed partner finance baseline"
call scripts\seed_partner_money_e2e.cmd >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto fail

call :log "[2.2/10] partner token"
set "PARTNER_LOGIN_FILE=%TEMP%\\admin_explain_partner_login_%RANDOM%.json"
set "PARTNER_LOGIN_BODY_FILE=%TEMP%\\admin_explain_partner_login_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PARTNER_LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','password': r'%PARTNER_PASSWORD%','portal':'partner'}), encoding='utf-8')"
set "AUTH_HEADER="
call :curl_check "%AUTH_URL%/login" "%PARTNER_LOGIN_FILE%" "200" "%PARTNER_LOGIN_BODY_FILE%"
if errorlevel 1 goto fail
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%T"
if "%PARTNER_TOKEN%"=="" goto fail
set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

call :log "[2.3/10] create fresh payout request"
set "AUTH_HEADER=%PARTNER_AUTH_HEADER%"
call :curl_check "%CORE_URL%/partner/auth/verify" "partner_verify.txt" "204"
if errorlevel 1 goto fail
set "PAYOUT_PREVIEW_BODY_FILE=%TEMP%\\admin_explain_payout_preview_%RANDOM%.json"
set "PAYOUT_REQUEST_BODY_FILE=%TEMP%\\admin_explain_payout_request_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PAYOUT_PREVIEW_BODY_FILE%').write_text(json.dumps({'amount': 1000, 'currency': 'RUB'}), encoding='utf-8'); Path(r'%PAYOUT_REQUEST_BODY_FILE%').write_text(json.dumps({'amount': 1000, 'currency': 'RUB'}), encoding='utf-8')"
call :curl_check "%CORE_URL%/partner/payouts/preview" "partner_payout_preview.json" "200" "%PAYOUT_PREVIEW_BODY_FILE%"
if errorlevel 1 goto fail
call :curl_check "%CORE_URL%/partner/payouts/request" "partner_payout_request.json" "200 201" "%PAYOUT_REQUEST_BODY_FILE%"
if errorlevel 1 goto fail
for /f "usebackq delims=" %%P in (`python -c "import json; data=json.load(open('partner_payout_request.json', encoding='utf-8')); print(data.get('payout_request_id') or data.get('id') or '')"`) do set "PAYOUT_ID=%%P"
for /f "usebackq delims=" %%C in (`python -c "import json; data=json.load(open('partner_payout_request.json', encoding='utf-8')); print(data.get('correlation_id') or '')"`) do set "PAYOUT_CORRELATION_ID=%%C"
if "%PAYOUT_ID%"=="" goto fail
if "%PAYOUT_CORRELATION_ID%"=="" goto fail
set "AUTH_HEADER=%ADMIN_AUTH_HEADER%"

call :log "[3/10] admin me"
call :curl_check "%CORE_URL%/v1/admin/me" "admin_me.json" "200"
if errorlevel 1 goto fail

call :log "[4/10] runtime summary"
call :curl_check "%CORE_URL%/v1/admin/runtime/summary" "admin_runtime.json" "200"
if errorlevel 1 goto fail

call :log "[5/10] finance payouts"
call :curl_check "%CORE_URL%/v1/admin/finance/payouts" "finance_payouts.json" "200"
if errorlevel 1 goto fail

for /f "usebackq delims=" %%P in (`python -c "import json; data=json.load(open('finance_payouts.json', encoding='utf-8')); items=data.get('items') or data.get('payouts') or []; target=next((item for item in items if str(item.get('payout_id') or item.get('id') or '') == r'%PAYOUT_ID%'), None); print((target or {}).get('payout_id') or (target or {}).get('id') or '')"`) do set "PAYOUT_ID=%%P"
if "%PAYOUT_ID%"=="" goto fail

call :log "[6/10] payout detail"
call :curl_check "%CORE_URL%/v1/admin/finance/payouts/%PAYOUT_ID%" "finance_payout_detail.json" "200"
if errorlevel 1 goto fail

for /f "usebackq delims=" %%P in (`python -c "import json; data=json.load(open('finance_payout_detail.json')); settlement=data.get('settlement_snapshot') or {}; print(data.get('partner_id') or data.get('partner_org') or settlement.get('partner_org_id') or '')"`) do set "PARTNER_ID=%%P"
if "%PARTNER_ID%"=="" goto fail

call :log "[7/10] partner ledger + settlement snapshot"
call :curl_check "%CORE_URL%/v1/admin/partners/ledger?partner_org_id=%PARTNER_ID%" "partner_ledger.json" "200"
if errorlevel 1 goto fail
python -c "import json; data=json.load(open('finance_payout_detail.json', encoding='utf-8')); raise SystemExit(0 if data.get('settlement_snapshot') else 1)"
if errorlevel 1 goto fail

call :log "[8/10] approve payout explain response"
set "CORR_ID=%PAYOUT_CORRELATION_ID%"
set "APPROVE_BODY_FILE=%TEMP%\\admin_explain_approve_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%APPROVE_BODY_FILE%').write_text(json.dumps({'reason': 'smoke check', 'correlation_id': r'%CORR_ID%'}), encoding='utf-8')"
call :curl_check "%CORE_URL%/v1/admin/finance/payouts/%PAYOUT_ID%/approve" "payout_approve.json" "200" "%APPROVE_BODY_FILE%"
if errorlevel 1 goto fail

call :log "[9/10] legal update validation response"
set "LEGAL_BODY_FILE=%TEMP%\\admin_explain_legal_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LEGAL_BODY_FILE%').write_text(json.dumps({'status': 'PENDING_REVIEW'}), encoding='utf-8')"
call :curl_check "%CORE_URL%/v1/admin/legal/partners/%PARTNER_ID%/status" "legal_status.json" "400 422" "%LEGAL_BODY_FILE%"
if errorlevel 1 goto fail

call :log "[10/10] audit feed"
call :curl_check "%CORE_URL%/v1/admin/audit" "audit_feed.json" "200"
if errorlevel 1 goto fail

echo PASS >> "%LOG_FILE%"
echo PASS
exit /b 0
goto :eof

:fail
echo FAIL >> "%LOG_FILE%"
echo FAIL
exit /b 1

:curl_check
set "URL=%~1"
set "OUT=%~2"
set "ALLOWED=%~3"
set "BODY_FILE=%~4"
set "CODE="

if "%BODY_FILE%"=="" (
  if "%AUTH_HEADER%"=="" (
    curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" > "%TEMP%\\admin_explain_status.code" 2>> "%LOG_FILE%"
  ) else (
    curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\\admin_explain_status.code" 2>> "%LOG_FILE%"
  )
) else (
  if "%AUTH_HEADER%"=="" (
    curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" > "%TEMP%\\admin_explain_status.code" 2>> "%LOG_FILE%"
  ) else (
    curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" > "%TEMP%\\admin_explain_status.code" 2>> "%LOG_FILE%"
  )
)
set /p CODE=<"%TEMP%\\admin_explain_status.code"
echo %ALLOWED% | findstr /C:"%CODE%" >nul
if errorlevel 1 (
  >> "%LOG_FILE%" echo [FAIL] %URL% expected %ALLOWED% got %CODE%
  if exist "%OUT%" type "%OUT%" >> "%LOG_FILE%"
  exit /b 1
)
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
