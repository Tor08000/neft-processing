@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

set "SCRIPT_NAME=smoke_partner_core_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_PORTAL%"=="" set "CORE_PORTAL=%CORE_BASE%/portal"
if "%CORE_PARTNER%"=="" set "CORE_PARTNER=%CORE_BASE%/partner"
if "%CORE_ADMIN%"=="" set "CORE_ADMIN=%CORE_BASE%/v1/admin"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"

call "%~dp0seed_partner_money_e2e.cmd" >nul 2>nul || goto :fail

echo Starting %SCRIPT_NAME%
echo BASE_URL=%BASE_URL%
echo CORE_PORTAL=%CORE_PORTAL%
echo CORE_PARTNER=%CORE_PARTNER%
echo AUTH_URL=%AUTH_URL%

set "PARTNER_LOGIN_FILE=%TEMP%\partner_core_login.json"
set "PARTNER_LOGIN_BODY_FILE=%TEMP%\partner_core_login_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PARTNER_LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','password': r'%PARTNER_PASSWORD%','portal':'partner'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%PARTNER_LOGIN_BODY_FILE%" "200" "%PARTNER_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%t"
if "%PARTNER_TOKEN%"=="" goto :fail

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

set "PARTNER_ME_FILE=%TEMP%\partner_core_me.json"
call :http_request "GET" "%CORE_PORTAL%/me" "%PARTNER_AUTH_HEADER%" "" "200" "%PARTNER_ME_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PARTNER_ME_FILE%')); print(str((data.get('actor_type') or '')).lower())"`) do set "ACTOR_TYPE=%%t"
if /i not "%ACTOR_TYPE%"=="partner" goto :fail
findstr /C:"PARTNER_FINANCE_VIEW" "%PARTNER_ME_FILE%" >nul || goto :fail
findstr /C:"PARTNER_PAYOUT_REQUEST" "%PARTNER_ME_FILE%" >nul || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%PARTNER_ME_FILE%')); org=data.get('org') or {}; print(org.get('id') or data.get('org_id') or '')"`) do set "ORG_ID=%%t"
if "%ORG_ID%"=="" goto :fail

set "FINANCE_DASHBOARD_FILE=%TEMP%\partner_core_finance_dashboard.json"
call :http_request "GET" "%CORE_PARTNER%/finance/dashboard" "%PARTNER_AUTH_HEADER%" "" "200" "%FINANCE_DASHBOARD_FILE%" || goto :fail

set "BALANCE_FILE=%TEMP%\partner_core_balance.json"
call :http_request "GET" "%CORE_PARTNER%/balance" "%PARTNER_AUTH_HEADER%" "" "200" "%BALANCE_FILE%" || goto :fail

set "LEDGER_FILE=%TEMP%\partner_core_ledger.json"
call :http_request "GET" "%CORE_PARTNER%/ledger?limit=5" "%PARTNER_AUTH_HEADER%" "" "200" "%LEDGER_FILE%" || goto :fail

set "PAYOUTS_FILE=%TEMP%\partner_core_payouts.json"
call :http_request "GET" "%CORE_PARTNER%/payouts" "%PARTNER_AUTH_HEADER%" "" "200" "%PAYOUTS_FILE%" || goto :fail

set "INVOICES_FILE=%TEMP%\partner_core_invoices.json"
call :http_request "GET" "%CORE_PARTNER%/invoices" "%PARTNER_AUTH_HEADER%" "" "200" "%INVOICES_FILE%" || goto :fail

set "ACTS_FILE=%TEMP%\partner_core_acts.json"
call :http_request "GET" "%CORE_PARTNER%/acts" "%PARTNER_AUTH_HEADER%" "" "200" "%ACTS_FILE%" || goto :fail

set "PROFILE_FILE=%TEMP%\partner_core_profile.json"
call :http_request "GET" "%CORE_PARTNER%/self-profile" "%PARTNER_AUTH_HEADER%" "" "200" "%PROFILE_FILE%" || goto :fail

set "SUPPORT_FILE=%TEMP%\partner_core_cases.json"
call :http_request "GET" "%CORE_BASE%/cases?limit=5" "%PARTNER_AUTH_HEADER%" "" "200" "%SUPPORT_FILE%" || goto :fail

echo E2E_PARTNER_CORE: PASS
exit /b 0

:fail
echo E2E_PARTNER_CORE: FAIL
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
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
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
