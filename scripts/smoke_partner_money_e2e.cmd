@echo off
setlocal EnableExtensions EnableDelayedExpansion
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
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=partner"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

call "%~dp0seed_partner_money_e2e.cmd" >nul 2>nul
if errorlevel 1 goto :fail

set "PARTNER_LOGIN_FILE=%TEMP%\partner_login.json"
set "PARTNER_TOKEN_FILE=%TEMP%\partner_token.txt"
set "PARTNER_LOGIN_BODY={\"email\":\"%PARTNER_EMAIL%\",\"password\":\"%PARTNER_PASSWORD%\",\"portal\":\"partner\"}"
call :http_request "POST" "%AUTH_URL%/login" "" "%PARTNER_LOGIN_BODY%" "200" "%PARTNER_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%PARTNER_TOKEN_FILE%').write_text(token); print(token)"`) do set "PARTNER_TOKEN=%%t"
if "%PARTNER_TOKEN%"=="" goto :fail

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

call :http_request "GET" "%CORE_PARTNER%/auth/verify" "%PARTNER_AUTH_HEADER%" "" "204" "%TEMP%\partner_verify.json" || goto :fail

set "PARTNER_ME_FILE=%TEMP%\partner_me.json"
call :http_request "GET" "%CORE_PORTAL%/me" "%PARTNER_AUTH_HEADER%" "" "200" "%PARTNER_ME_FILE%" || goto :fail

call :http_request "GET" "%CORE_PARTNER%/ledger?limit=5" "%PARTNER_AUTH_HEADER%" "" "200" "%TEMP%\partner_ledger.json" || goto :fail

set "PAYOUT_REQUEST_FILE=%TEMP%\payout_request.json"
set "PAYOUT_PAYLOAD={\"amount\":1000,\"currency\":\"RUB\"}"
call :http_request "POST" "%CORE_PARTNER%/payouts/request" "%PARTNER_AUTH_HEADER%" "%PAYOUT_PAYLOAD%" "200,201" "%PAYOUT_REQUEST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PAYOUT_REQUEST_FILE%')); print(data.get('payout_request_id') or data.get('id') or '')"`) do set "PAYOUT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%PAYOUT_REQUEST_FILE%')).get('correlation_id',''))"`) do set "CORRELATION_ID=%%t"
if "%PAYOUT_ID%"=="" goto :fail
if "%CORRELATION_ID%"=="" goto :fail

set "ADMIN_LOGIN_FILE=%TEMP%\admin_login.json"
set "ADMIN_TOKEN_FILE=%TEMP%\admin_token.txt"
set "ADMIN_LOGIN_BODY={\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\",\"portal\":\"admin\"}"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%ADMIN_TOKEN_FILE%').write_text(token); print(token)"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" goto :fail

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

set "ADMIN_APPROVE_FILE=%TEMP%\admin_approve.json"
set "APPROVE_PAYLOAD={\"reason\":\"Smoke approval\",\"correlation_id\":\"%CORRELATION_ID%\"}"
call :http_request "POST" "%CORE_ADMIN_FINANCE_URL%/payouts/%PAYOUT_ID%/approve" "%ADMIN_AUTH_HEADER%" "%APPROVE_PAYLOAD%" "200" "%ADMIN_APPROVE_FILE%" || goto :fail

call :http_request "GET" "%CORE_PARTNER%/payouts/%PAYOUT_ID%" "%PARTNER_AUTH_HEADER%" "" "200" "%TEMP%\partner_payout_detail.json" || goto :fail

set "AUDIT_FILE=%TEMP%\audit.json"
call :http_request "GET" "%CORE_ADMIN_AUDIT_URL%?correlation_id=%CORRELATION_ID%" "%ADMIN_AUTH_HEADER%" "" "200" "%AUDIT_FILE%" || goto :fail

echo E2E_PARTNER_MONEY: PASS
exit /b 0

:fail
echo E2E_PARTNER_MONEY: FAIL
exit /b 1

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\%SCRIPT_NAME%_resp_%RANDOM%.json"
if "%BODY%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "%BODY%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
)
if "%CODE%"=="" exit /b 1
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if defined MATCHED exit /b 0
exit /b 1
