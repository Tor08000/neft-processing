@echo off
setlocal enabledelayedexpansion

REM Defaults can be overridden in .env
set "ENV_FILE=.env"
set "ADMIN_EMAIL=admin@example.com"
set "ADMIN_PASSWORD=admin123"
set "AUTH_BASE_URL=http://localhost"
set "AUTH_ADMIN_URL="

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
        if /I "%%A"=="AUTH_BASE_URL" set "AUTH_BASE_URL=%%B"
        if /I "%%A"=="AUTH_ADMIN_URL" set "AUTH_ADMIN_URL=%%B"
        if /I "%%A"=="ADMIN_AUTH_URL" set "AUTH_ADMIN_URL=%%B"
    )
)

set "HEADER_FILE=%TEMP%\\admin_login_headers_%RANDOM%.tmp"
set "BODY_FILE=%TEMP%\\admin_login_body_%RANDOM%.tmp"
set "OPENAPI_FILE=%TEMP%\\auth_openapi_%RANDOM%.tmp"

set "TOKEN="
set "STATUS="
if defined AUTH_ADMIN_URL (
    if not "%AUTH_ADMIN_URL:/login=%"=="%AUTH_ADMIN_URL%" (
        set "LOGIN_URL=%AUTH_ADMIN_URL%"
    ) else (
        set "AUTH_BASE_URL=%AUTH_ADMIN_URL%"
    )
)

if not defined LOGIN_URL (
    curl -sS -o "%OPENAPI_FILE%" "%AUTH_BASE_URL%/api/auth/openapi.json"
    if errorlevel 1 (
        echo [ERROR] Failed to fetch OpenAPI spec. 1>&2
        echo URL: %AUTH_BASE_URL%/api/auth/openapi.json 1>&2
        exit /b 1
    )
    for /f "usebackq delims=" %%U in (`python -c "import json; data=json.load(open(r'%OPENAPI_FILE%','r',encoding='utf-8')); paths=data.get('paths',{}); candidates=[p for p,m in paths.items() if 'post' in m and p.endswith('/login')]; candidates=sorted(candidates, key=lambda p: (0 if '/api/auth/' in p else 1, len(p))); print(candidates[0] if candidates else '')"`) do set "LOGIN_PATH=%%U"
    if not defined LOGIN_PATH (
        echo [ERROR] Login endpoint not found in OpenAPI spec. 1>&2
        echo --- OpenAPI preview (first 80 lines) --- 1>&2
        python -c "from pathlib import Path;lines=Path(r'%OPENAPI_FILE%').read_text(encoding='utf-8',errors='ignore').splitlines();print('\n'.join(lines[:80]))" 1>&2
        exit /b 1
    )
    set "LOGIN_URL=%AUTH_BASE_URL%%LOGIN_PATH%"
)

set "STATUS="
curl -sS -D "%HEADER_FILE%" -o "%BODY_FILE%" -X POST -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}" "%LOGIN_URL%"
if errorlevel 1 (
    echo [ERROR] Failed to request admin token. 1>&2
    echo URL: %LOGIN_URL% 1>&2
    echo Email: %ADMIN_EMAIL% 1>&2
    echo HTTP status: !STATUS! 1>&2
    if exist "%BODY_FILE%" type "%BODY_FILE%" 1>&2
    exit /b 1
)

for /f "usebackq delims=" %%A in (`python -c "import re;from pathlib import Path;data=Path(r'%HEADER_FILE%').read_text(encoding='utf-8',errors='ignore');matches=re.findall(r'^HTTP/\\S+\\s+(\\d+)', data, flags=re.M);print(matches[-1] if matches else '')"`) do set "STATUS=%%A"
if not "%STATUS%"=="200" (
    echo [ERROR] Admin token request failed. 1>&2
    echo URL: %LOGIN_URL% 1>&2
    echo Email: %ADMIN_EMAIL% 1>&2
    echo HTTP status: %STATUS% 1>&2
    type "%BODY_FILE%" 1>&2
    exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json;print(json.load(open(r'%BODY_FILE%','r',encoding='utf-8')).get('access_token',''))"`) do set "TOKEN=%%T"
if "%TOKEN%"=="" (
    echo [ERROR] No access_token returned. 1>&2
    echo URL: %LOGIN_URL% 1>&2
    echo Email: %ADMIN_EMAIL% 1>&2
    echo HTTP status: %STATUS% 1>&2
    type "%BODY_FILE%" 1>&2
    exit /b 1
)

if not defined TOKEN exit /b 1

endlocal & echo %TOKEN%
