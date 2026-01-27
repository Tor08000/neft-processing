@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "SCRIPT_NAME=smoke_all_portals"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_ADMIN%"=="" set "CORE_ADMIN=%CORE_BASE%/v1/admin"

if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=client"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=partner"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

call "%~dp0smoke_partner_money_e2e.cmd" >nul 2>nul
if errorlevel 1 goto :fail

set "CLIENT_LOGIN_FILE=%TEMP%\client_login.json"
set "CLIENT_LOGIN_BODY={\"email\":\"%CLIENT_EMAIL%\",\"password\":\"%CLIENT_PASSWORD%\",\"portal\":\"client\"}"
call :http_request "POST" "%AUTH_URL%/login" "" "%CLIENT_LOGIN_BODY%" "200" "%CLIENT_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%t"
if "%CLIENT_TOKEN%"=="" goto :fail

set "CLIENT_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
call :http_request "GET" "%CORE_BASE%/portal/me" "%CLIENT_HEADER%" "" "200" "%TEMP%\client_me.json" || goto :fail

set "ADMIN_LOGIN_FILE=%TEMP%\admin_login.json"
set "ADMIN_LOGIN_BODY={\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\",\"portal\":\"admin\"}"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" goto :fail

set "ADMIN_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
call :http_request "GET" "%CORE_ADMIN%/me" "%ADMIN_HEADER%" "" "200" "%TEMP%\admin_me.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/runtime/summary" "%ADMIN_HEADER%" "" "200" "%TEMP%\admin_runtime.json" || goto :fail
call :http_request "GET" "%CORE_ADMIN%/finance/payouts" "%ADMIN_HEADER%" "" "200" "%TEMP%\admin_payouts.json" || goto :fail

echo SMOKE_ALL_PORTALS: PASS
exit /b 0

:fail
echo SMOKE_ALL_PORTALS: FAIL
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
