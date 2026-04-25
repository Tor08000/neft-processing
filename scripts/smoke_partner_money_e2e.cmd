@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

set "SCRIPT_NAME=smoke_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_PORTAL%"=="" set "CORE_PORTAL=%CORE_BASE%/portal"
if "%CORE_PARTNER%"=="" set "CORE_PARTNER=%CORE_BASE%/partner"
if "%CORE_ADMIN%"=="" set "CORE_ADMIN=%CORE_BASE%/v1/admin"
if "%CORE_ADMIN_FINANCE_URL%"=="" set "CORE_ADMIN_FINANCE_URL=%CORE_ADMIN%/finance"
if "%CORE_ADMIN_AUDIT_URL%"=="" set "CORE_ADMIN_AUDIT_URL=%CORE_ADMIN%/audit"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"

set "LAST_STEP=seed_partner_money"
call "%~dp0seed_partner_money_e2e.cmd" >nul 2>nul || goto :fail

set "PARTNER_LOGIN_FILE=%TEMP%\partner_login.json"
set "PARTNER_TOKEN_FILE=%TEMP%\partner_token.txt"
set "PARTNER_LOGIN_BODY_FILE=%TEMP%\partner_login_body_%RANDOM%.json"
set "LAST_STEP=partner_login_body"
python -c "import json; from pathlib import Path; Path(r'%PARTNER_LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','password': r'%PARTNER_PASSWORD%','portal':'partner'}), encoding='utf-8')"
if errorlevel 1 goto :fail
set "LAST_STEP=partner_login_request"
call :http_request "POST" "%AUTH_URL%/login" "" "%PARTNER_LOGIN_BODY_FILE%" "200" "%PARTNER_LOGIN_FILE%" || goto :fail
set "LAST_STEP=partner_login_token"
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%PARTNER_TOKEN_FILE%').write_text(token, encoding='utf-8')"
if errorlevel 1 goto :fail
set /p PARTNER_TOKEN=<"%PARTNER_TOKEN_FILE%"
if "%PARTNER_TOKEN%"=="" goto :fail

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

call :http_request "GET" "%CORE_PARTNER%/auth/verify" "%PARTNER_AUTH_HEADER%" "" "204" "%TEMP%\partner_verify.json" || goto :fail

set "PARTNER_ME_FILE=%TEMP%\partner_me.json"
call :http_request "GET" "%CORE_PORTAL%/me" "%PARTNER_AUTH_HEADER%" "" "200" "%PARTNER_ME_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PARTNER_ME_FILE%')); print(str((data.get('actor_type') or '')).lower())"`) do set "ACTOR_TYPE=%%t"
if /i not "%ACTOR_TYPE%"=="partner" goto :fail

set "PARTNER_LEDGER_FILE=%TEMP%\partner_ledger.json"
call :http_request "GET" "%CORE_PARTNER%/ledger?limit=5" "%PARTNER_AUTH_HEADER%" "" "200" "%PARTNER_LEDGER_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PARTNER_LEDGER_FILE%')); items=data.get('items') or data.get('entries') or []; totals=data.get('totals') or {}; print(bool(items) or bool(totals))"`) do set "LEDGER_OK=%%t"
if /i not "%LEDGER_OK%"=="True" goto :fail

set "PAYOUT_PREVIEW_FILE=%TEMP%\partner_payout_preview.json"
set "PAYOUT_PREVIEW_PAYLOAD_FILE=%TEMP%\partner_payout_preview_payload_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PAYOUT_PREVIEW_PAYLOAD_FILE%').write_text(json.dumps({'amount': 1000, 'currency': 'RUB'}), encoding='utf-8')"
call :http_request "POST" "%CORE_PARTNER%/payouts/preview" "%PARTNER_AUTH_HEADER%" "%PAYOUT_PREVIEW_PAYLOAD_FILE%" "200" "%PAYOUT_PREVIEW_FILE%" || goto :fail

set "PAYOUT_REQUEST_FILE=%TEMP%\partner_payout_request.json"
set "PAYOUT_PAYLOAD_FILE=%TEMP%\partner_payout_payload_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PAYOUT_PAYLOAD_FILE%').write_text(json.dumps({'amount': 1000, 'currency': 'RUB'}), encoding='utf-8')"
call :http_request "POST" "%CORE_PARTNER%/payouts/request" "%PARTNER_AUTH_HEADER%" "%PAYOUT_PAYLOAD_FILE%" "200,201" "%PAYOUT_REQUEST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PAYOUT_REQUEST_FILE%')); print(data.get('payout_request_id') or data.get('id') or '')"`) do set "PAYOUT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%PAYOUT_REQUEST_FILE%')).get('correlation_id',''))"`) do set "CORRELATION_ID=%%t"
if "%PAYOUT_ID%"=="" goto :fail
if "%CORRELATION_ID%"=="" goto :fail

set "ADMIN_LOGIN_FILE=%TEMP%\admin_login.json"
set "ADMIN_TOKEN_FILE=%TEMP%\admin_token.txt"
set "ADMIN_LOGIN_BODY_FILE=%TEMP%\admin_login_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%ADMIN_LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY_FILE%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
set "LAST_STEP=admin_login_token"
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%ADMIN_TOKEN_FILE%').write_text(token, encoding='utf-8')"
if errorlevel 1 goto :fail
set /p ADMIN_TOKEN=<"%ADMIN_TOKEN_FILE%"
if "%ADMIN_TOKEN%"=="" goto :fail

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "ADMIN_APPROVE_FILE=%TEMP%\admin_approve.json"
set "APPROVE_PAYLOAD_FILE=%TEMP%\admin_approve_payload_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%APPROVE_PAYLOAD_FILE%').write_text(json.dumps({'reason': 'Smoke approval', 'correlation_id': r'%CORRELATION_ID%'}), encoding='utf-8')"
call :http_request "POST" "%CORE_ADMIN_FINANCE_URL%/payouts/%PAYOUT_ID%/approve" "%ADMIN_AUTH_HEADER%" "%APPROVE_PAYLOAD_FILE%" "200" "%ADMIN_APPROVE_FILE%" || goto :fail

set "PAYOUT_DETAIL_FILE=%TEMP%\partner_payout_detail.json"
call :http_request "GET" "%CORE_PARTNER%/payouts/%PAYOUT_ID%" "%PARTNER_AUTH_HEADER%" "" "200" "%PAYOUT_DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PAYOUT_DETAIL_FILE%')); status=str(data.get('status') or '').upper(); print(status)"`) do set "PAYOUT_STATUS=%%t"
if /i not "%PAYOUT_STATUS%"=="APPROVED" if /i not "%PAYOUT_STATUS%"=="PAID" goto :fail

set "AUDIT_FILE=%TEMP%\admin_audit.json"
call :http_request "GET" "%CORE_ADMIN_AUDIT_URL%?correlation_id=%CORRELATION_ID%" "%ADMIN_AUTH_HEADER%" "" "200" "%AUDIT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%AUDIT_FILE%')); items=data.get('items') or data.get('events') or []; print(bool(items))"`) do set "AUDIT_OK=%%t"
if /i not "%AUDIT_OK%"=="True" goto :fail

echo E2E_PARTNER_MONEY: PASS
exit /b 0

:fail
echo E2E_PARTNER_MONEY: FAIL step=%LAST_STEP%
exit /b 1

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\%SCRIPT_NAME%_resp_%RANDOM%.json"
if "%BODY_FILE%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
)
if "%CODE%"=="" (
  echo [HTTP FAIL] %METHOD% %URL% expected %EXPECTED% got empty_status
  if exist "%OUT%" type "%OUT%"
  exit /b 1
)
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if defined MATCHED exit /b 0
echo [HTTP FAIL] %METHOD% %URL% expected %EXPECTED% got %CODE%
if exist "%OUT%" type "%OUT%"
exit /b 1
