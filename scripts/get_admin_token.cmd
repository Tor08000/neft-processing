@echo off
setlocal enabledelayedexpansion

REM Defaults can be overridden in .env
set "ENV_FILE=.env"
set "ADMIN_EMAIL=admin@example.com"
set "ADMIN_PASSWORD=admin123"
set "AUTH_ADMIN_URL=http://localhost/api/auth/api/v1/auth/login"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
        if /I "%%A"=="AUTH_ADMIN_URL" set "AUTH_ADMIN_URL=%%B"
        if /I "%%A"=="ADMIN_AUTH_URL" set "AUTH_ADMIN_URL=%%B"
    )
)

set "HEADER_FILE=%TEMP%\\admin_login_headers_%RANDOM%.tmp"
set "BODY_FILE=%TEMP%\\admin_login_body_%RANDOM%.tmp"

curl -sS -D "%HEADER_FILE%" -o "%BODY_FILE%" -X POST -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}" "%AUTH_ADMIN_URL%"
if errorlevel 1 (
    echo [ERROR] Failed to request admin token. 1>&2
    echo URL: %AUTH_ADMIN_URL% 1>&2
    echo Email: %ADMIN_EMAIL% 1>&2
    exit /b 1
)

set "STATUS="
for /f "tokens=2 delims= " %%A in ('findstr /R /C:"^HTTP/" "%HEADER_FILE%"') do set "STATUS=%%A"

if not "%STATUS%"=="200" (
    echo [ERROR] Admin token request failed. 1>&2
    echo URL: %AUTH_ADMIN_URL% 1>&2
    echo Email: %ADMIN_EMAIL% 1>&2
    echo HTTP status: %STATUS% 1>&2
    type "%BODY_FILE%" 1>&2
    exit /b 1
)

set "TOKEN="
for /f "usebackq delims=" %%T in (`python -c "import json;print(json.load(open(r'%BODY_FILE%','r',encoding='utf-8')).get('access_token',''))"`) do set "TOKEN=%%T"

if "%TOKEN%"=="" (
    echo [ERROR] No access_token returned. 1>&2
    echo URL: %AUTH_ADMIN_URL% 1>&2
    echo Email: %ADMIN_EMAIL% 1>&2
    echo HTTP status: %STATUS% 1>&2
    type "%BODY_FILE%" 1>&2
    exit /b 1
)

endlocal & echo %TOKEN%
