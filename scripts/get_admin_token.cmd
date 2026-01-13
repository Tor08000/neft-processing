@echo off
setlocal enabledelayedexpansion

REM Defaults can be overridden in .env
set "ENV_FILE=.env"
set "ADMIN_EMAIL=admin@example.com"
set "ADMIN_PASSWORD=change-me"
set "DIRECT_BASE=http://localhost:8002"
set "GATEWAY_BASE=http://localhost"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
    )
)

set "HEADER_FILE=%TEMP%\\admin_login_headers_%RANDOM%.tmp"
set "BODY_FILE=%TEMP%\\auth_body.json"
set "OPENAPI_FILE=%TEMP%\\auth_openapi_%RANDOM%.tmp"
set "MAX_BODY_CHARS=1000"

set "TOKEN="
set "STATUS="

curl -sS -o "%OPENAPI_FILE%" "%DIRECT_BASE%/api/auth/openapi.json"
if errorlevel 1 (
    set "ERROR_MESSAGE=[ERROR] Failed to fetch OpenAPI spec."
    set "ERROR_URL=%DIRECT_BASE%/api/auth/openapi.json"
    goto :error_fetch_openapi
)
for /f "usebackq delims=" %%U in (`python -c "import json; data=json.load(open(r'%OPENAPI_FILE%','r',encoding='utf-8')); paths=data.get('paths',{}); candidates=[p for p,m in paths.items() if isinstance(m,dict) and any(k.lower()=='post' for k in m.keys()) and ('login' in p.lower() or 'token' in p.lower())]; candidates=sorted(candidates); print(candidates[0] if candidates else '')"`) do set "LOGIN_PATH=%%U"
if not defined LOGIN_PATH (
    set "ERROR_MESSAGE=[ERROR] Login endpoint not found in OpenAPI spec."
    goto :error_openapi_login
)

if not "%LOGIN_PATH:~0,1%"=="/" set "LOGIN_PATH=/%LOGIN_PATH%"
set "GATEWAY_URL=%GATEWAY_BASE%%LOGIN_PATH%"
set "DIRECT_URL=%DIRECT_BASE%%LOGIN_PATH%"

set "ERROR_LOGIN_PATH=%LOGIN_PATH%"
set "ERROR_GATEWAY_URL=%GATEWAY_URL%"
set "ERROR_DIRECT_URL=%DIRECT_URL%"

call :request_token "%GATEWAY_URL%"
set "REQUEST_RESULT=%ERRORLEVEL%"
if "%REQUEST_RESULT%"=="2" (
    call :request_token "%DIRECT_URL%"
    set "REQUEST_RESULT=%ERRORLEVEL%"
)
if "%REQUEST_RESULT%"=="2" (
    set "ERROR_MESSAGE=[ERROR] Login endpoint returned 404 on gateway and direct."
    set "ERROR_URL=%DIRECT_URL%"
    set "ERROR_EMAIL=%ADMIN_EMAIL%"
    set "ERROR_STATUS=404"
    set "ERROR_BODY_FILE=%BODY_FILE%"
    goto :error_request_token
)
if not "%REQUEST_RESULT%"=="0" (
    goto :error_request_token
)

endlocal & echo %TOKEN%

exit /b 0

:error_fetch_openapi
1>&2 echo %ERROR_MESSAGE%
1>&2 echo URL: %ERROR_URL%
exit /b 1

:error_openapi_login
1>&2 echo %ERROR_MESSAGE%
python -c "import json; data=json.load(open(r'%OPENAPI_FILE%','r',encoding='utf-8')); paths=data.get('paths',{}); candidates=sorted(p for p,m in paths.items() if isinstance(m,dict) and any(k.lower()=='post' for k in m.keys())); print('\n'.join(candidates))" 1>&2
exit /b 1

:error_request_token
1>&2 echo %ERROR_MESSAGE%
if defined ERROR_LOGIN_PATH 1>&2 echo LOGIN_PATH: %ERROR_LOGIN_PATH%
if defined ERROR_URL 1>&2 echo URL: %ERROR_URL%
if defined ERROR_EMAIL 1>&2 echo Email: %ERROR_EMAIL%
if defined ERROR_STATUS 1>&2 echo HTTP status: %ERROR_STATUS%
if defined ERROR_BODY_FILE (
    if exist "%ERROR_BODY_FILE%" python -c "from pathlib import Path; text=Path(r'%ERROR_BODY_FILE%').read_text(encoding='utf-8',errors='ignore'); max_len=int(r'%MAX_BODY_CHARS%'); print(text[:max_len])" 1>&2
)
exit /b 1

:request_token
set "LOGIN_URL=%~1"
set "STATUS="
set "TOKEN="

curl -sS -D "%HEADER_FILE%" -o "%BODY_FILE%" -X POST -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}" "%LOGIN_URL%"
if errorlevel 1 (
    set "ERROR_MESSAGE=Failed to request admin token."
    set "ERROR_URL=%LOGIN_URL%"
    set "ERROR_EMAIL=%ADMIN_EMAIL%"
    set "ERROR_STATUS=!STATUS!"
    set "ERROR_BODY_FILE=%BODY_FILE%"
    exit /b 1
)

for /f "usebackq delims=" %%A in (`python -c "import re;from pathlib import Path;data=Path(r'%HEADER_FILE%').read_text(encoding='utf-8',errors='ignore');matches=re.findall(r'^HTTP/\\S+\\s+(\\d+)', data, flags=re.M);print(matches[-1] if matches else '')"`) do set "STATUS=%%A"

for /f "usebackq delims=" %%T in (`python -c "import json;from pathlib import Path; p=Path(r'%BODY_FILE%');\ntry:\n    data=json.loads(p.read_text(encoding='utf-8',errors='ignore'))\nexcept Exception:\n    data={}\nprint(data.get('access_token',''))"`) do set "TOKEN=%%T"
if not "%TOKEN%"=="" exit /b 0
if "%STATUS%"=="404" exit /b 2
set "ERROR_MESSAGE=Admin token request failed."
set "ERROR_URL=%LOGIN_URL%"
set "ERROR_EMAIL=%ADMIN_EMAIL%"
set "ERROR_STATUS=%STATUS%"
set "ERROR_BODY_FILE=%BODY_FILE%"
exit /b 1

exit /b 0
