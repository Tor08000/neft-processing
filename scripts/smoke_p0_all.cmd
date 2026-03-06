@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "SCRIPT_NAME=smoke_p0_all"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_PORTAL%"=="" set "CORE_PORTAL=%CORE_BASE%/portal"
if "%CORE_CLIENT%"=="" set "CORE_CLIENT=%CORE_BASE%/client"
if "%CORE_PARTNER%"=="" set "CORE_PARTNER=%CORE_BASE%/partner"
if "%CORE_ADMIN%"=="" set "CORE_ADMIN=%CORE_BASE%/v1/admin"
if "%CORE_ADMIN_VERIFY%"=="" set "CORE_ADMIN_VERIFY=%CORE_BASE%/admin/auth/verify"

if "%CLIENT_EMAIL%"=="" (
  for /f "usebackq tokens=*" %%t in (`python -c "import uuid; print(f'client-smoke-{uuid.uuid4().hex[:8]}@neft.local')"` ) do set "CLIENT_EMAIL=%%t"
)
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=client"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

set "CLIENT_SIGNUP_FILE=%TEMP%\client_signup.json"
set "CLIENT_SIGNUP_BODY_FILE=%TEMP%\client_signup_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%CLIENT_SIGNUP_BODY_FILE%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%','password': r'%CLIENT_PASSWORD%','full_name': 'Client Smoke'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/signup" "" "%CLIENT_SIGNUP_BODY_FILE%" "200,201,409" "%CLIENT_SIGNUP_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%CLIENT_SIGNUP_FILE%', encoding='utf-8', errors='ignore')); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%t"
if "%CLIENT_TOKEN%"=="" (
  call :login "%CLIENT_EMAIL%" "%CLIENT_PASSWORD%" "client" CLIENT_TOKEN || goto :fail
)

set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

set "CLIENT_PORTAL_FILE=%TEMP%\client_portal_me.json"
call :http_request "GET" "%CORE_PORTAL%/me" "%CLIENT_AUTH_HEADER%" "" "200" "%CLIENT_PORTAL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%CLIENT_PORTAL_FILE%')); print(str(data.get('access_state') or ''))"`) do set "CLIENT_ACCESS_STATE=%%t"
if /i "%CLIENT_ACCESS_STATE%"=="TECH_ERROR" goto :fail

set "CLIENT_PROFILE_BODY_FILE=%TEMP%\client_profile_body_%RANDOM%.json"
set "CLIENT_PROFILE_FILE=%TEMP%\client_profile.json"
python -c "import json; from pathlib import Path; Path(r'%CLIENT_PROFILE_BODY_FILE%').write_text(json.dumps({'org_type': 'LEGAL','name': 'ООО Клиент Смоук','inn': '7707083893'}), encoding='utf-8')"
call :http_request "POST" "%CORE_CLIENT%/onboarding/profile" "%CLIENT_AUTH_HEADER%" "%CLIENT_PROFILE_BODY_FILE%" "200" "%CLIENT_PROFILE_FILE%" || goto :fail

set "CLIENT_PORTAL_AFTER_FILE=%TEMP%\client_portal_me_after.json"
call :http_request "GET" "%CORE_PORTAL%/me" "%CLIENT_AUTH_HEADER%" "" "200" "%CLIENT_PORTAL_AFTER_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%CLIENT_PORTAL_AFTER_FILE%')); state=str(data.get('access_state') or '').upper(); print(state)"`) do set "CLIENT_ACCESS_STATE_AFTER=%%t"
if /i not "%CLIENT_ACCESS_STATE_AFTER%"=="NEEDS_PLAN" if /i not "%CLIENT_ACCESS_STATE_AFTER%"=="NEEDS_CONTRACT" goto :fail

call :login "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" "partner" PARTNER_TOKEN || goto :fail
set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

call :http_request "GET" "%CORE_PARTNER%/auth/verify" "%PARTNER_AUTH_HEADER%" "" "204" "%TEMP%\partner_verify.json" || goto :fail
call :http_request "GET" "%CORE_PORTAL%/me" "%PARTNER_AUTH_HEADER%" "" "200" "%TEMP%\partner_portal_me.json" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%TEMP%\partner_portal_me.json')); print(str((data.get('actor_type') or '')).lower())"`) do set "PARTNER_ACTOR=%%t"
if /i not "%PARTNER_ACTOR%"=="partner" goto :fail
call :http_request "GET" "%CORE_PARTNER%/dashboard" "%PARTNER_AUTH_HEADER%" "" "200" "%TEMP%\partner_dashboard.json" || goto :fail
call :http_request "GET" "%CORE_PARTNER%/ledger?limit=5" "%PARTNER_AUTH_HEADER%" "" "200" "%TEMP%\partner_ledger.json" || goto :fail

call :login "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "admin" ADMIN_TOKEN || goto :fail
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

call :http_request "GET" "%CORE_ADMIN_VERIFY%" "%ADMIN_AUTH_HEADER%" "" "204" "%TEMP%\admin_verify.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/me" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_me.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/runtime/summary" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_runtime.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/ops/summary" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_ops.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/finance/overview?window=24h" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_finance_overview.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/audit" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_audit.json" || goto :fail

echo SMOKE_P0_ALL: PASS
exit /b 0

:fail
echo SMOKE_P0_ALL: FAIL
exit /b 1

:login
set "EMAIL=%~1"
set "PASSWORD=%~2"
set "PORTAL=%~3"
set "TOKEN_VAR=%~4"
set "LOGIN_BODY_FILE=%TEMP%\login_body_%RANDOM%.json"
set "LOGIN_FILE=%TEMP%\login_resp_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%EMAIL%','password': r'%PASSWORD%','portal': r'%PORTAL%'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_FILE%" || exit /b 1
for /f "usebackq tokens=*" %%t in (`python -c "import json; data=json.load(open(r'%LOGIN_FILE%', encoding='utf-8', errors='ignore')); print(data.get('access_token',''))"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" exit /b 1
set "%TOKEN_VAR%=%TOKEN%"
exit /b 0

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
if "%CODE%"=="" exit /b 1
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if defined MATCHED exit /b 0
exit /b 1
