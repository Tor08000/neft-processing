@echo off
setlocal EnableExtensions DisableDelayedExpansion

if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" (
      if not "%%A:~0,1"=="#" (
        if /I "%%A"=="GATEWAY_BASE_URL" set "BASE_URL=%%B"
        if /I "%%A"=="NEFT_BOOTSTRAP_CLIENT_EMAIL" set "CLIENT_EMAIL=%%B"
        if /I "%%A"=="NEFT_BOOTSTRAP_CLIENT_PASSWORD" set "CLIENT_PASSWORD=%%B"
      )
    )
  )
)

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_BASE_URL%"=="" set "AUTH_BASE_URL=%BASE_URL%"
if "%CORE_BASE_URL%"=="" set "CORE_BASE_URL=%BASE_URL%"
if "%CLIENT_EMAIL%"=="" (
  for /f "usebackq tokens=*" %%e in (`python -c "import uuid; print(f'client-portal-smoke-{uuid.uuid4().hex[:8]}@neft.local')"` ) do set "CLIENT_EMAIL=%%e"
)
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=ClientPortal123!"

echo ^>^>^> client portal root
call :http_request "GET" "%BASE_URL%/client/" "" "" "200" "%TEMP%\client_portal.html" || goto :fail
findstr /C:"<div id=\"root\"></div>" "%TEMP%\client_portal.html" >nul || goto :fail
echo.

echo ^>^>^> client portal favicon
call :http_request "GET" "%BASE_URL%/client/brand/favicon.svg" "" "" "200" "%TEMP%\client_favicon.svg" || goto :fail
findstr /C:"<svg" "%TEMP%\client_favicon.svg" >nul || goto :fail
echo.

echo ^>^>^> core health
call :http_request "GET" "%CORE_BASE_URL%/api/core/health" "" "" "200" "%TEMP%\core_health.json" || goto :fail
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TEMP%\\core_health.json').read_text(encoding='utf-8', errors='ignore') or '{}'); assert data.get('status') == 'ok', data"
if errorlevel 1 goto :fail
echo.

echo ^>^>^> auth health
call :http_request "GET" "%AUTH_BASE_URL%/api/v1/auth/health" "" "" "200" "%TEMP%\auth_health.json" || goto :fail
echo.

set "REGISTER_BODY_FILE=%TEMP%\client_portal_register_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%REGISTER_BODY_FILE%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%', 'password': r'%CLIENT_PASSWORD%', 'full_name': 'Client Portal Smoke'}), encoding='utf-8')"
echo ^>^>^> auth register
call :http_json_request "POST" "%AUTH_BASE_URL%/api/v1/auth/register" "%REGISTER_BODY_FILE%" "201,409" "%TEMP%\auth_register.json" || goto :fail
echo.

set "LOGIN_BODY_FILE=%TEMP%\client_portal_login_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%', 'password': r'%CLIENT_PASSWORD%', 'portal': 'client'}), encoding='utf-8')"
echo ^>^>^> auth login
call :http_json_request "POST" "%AUTH_BASE_URL%/api/v1/auth/login" "%LOGIN_BODY_FILE%" "200" "%TEMP%\auth_login.json" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TEMP%\\auth_login.json').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "AUTH_TOKEN=%%t"
if "%AUTH_TOKEN%"=="" goto :fail
echo.

echo ^>^>^> auth me
call :http_request "GET" "%AUTH_BASE_URL%/api/v1/auth/me" "Authorization: Bearer %AUTH_TOKEN%" "" "200" "%TEMP%\auth_me.json" || goto :fail
echo.

echo Client portal smoke checks passed.
del /q "%REGISTER_BODY_FILE%" "%LOGIN_BODY_FILE%" 2>nul
endlocal
exit /b 0

:fail
if exist "%TEMP%\auth_register.json" type "%TEMP%\auth_register.json" 1>&2
if exist "%TEMP%\auth_login.json" type "%TEMP%\auth_login.json" 1>&2
del /q "%REGISTER_BODY_FILE%" "%LOGIN_BODY_FILE%" 2>nul
endlocal
exit /b 1

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\smoke_client_portal_resp_%RANDOM%.txt"
if "%BODY%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl.exe -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl.exe -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl.exe -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "%BODY%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl.exe -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" "%URL%" 2^>nul`) do set "CODE=%%c"
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

:http_json_request
set "METHOD=%~1"
set "URL=%~2"
set "BODY_FILE=%~3"
set "EXPECTED=%~4"
set "OUT=%~5"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl.exe -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
if "%CODE%"=="" exit /b 1
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if defined MATCHED exit /b 0
exit /b 1
