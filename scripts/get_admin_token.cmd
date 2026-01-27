@echo off
setlocal enabledelayedexpansion

REM Defaults can be overridden in .env
set "ENV_FILE=.env"
set "ADMIN_EMAIL=admin@example.com"
set "ADMIN_PASSWORD=admin"
set "DIRECT_BASE=http://localhost:8002"
set "GATEWAY_BASE=http://localhost"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="NEFT_BOOTSTRAP_ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="NEFT_BOOTSTRAP_ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
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

curl -sS -o "%OPENAPI_FILE%" "%DIRECT_BASE%/api/v1/auth/openapi.json"
if errorlevel 1 (
    set "ERROR_MESSAGE=Failed to fetch OpenAPI spec."
    set "ERROR_URL=%DIRECT_BASE%/api/v1/auth/openapi.json"
    set "ERROR_STATUS="
    goto :emit_error_json
)
for /f "usebackq delims=" %%U in (`python -c "import json; data=json.load(open(r'%OPENAPI_FILE%','r',encoding='utf-8')); paths=data.get('paths',{}); candidates=[p for p,m in paths.items() if isinstance(m,dict) and any(k.lower()=='post' for k in m.keys()) and ('login' in p.lower() or 'token' in p.lower())]; candidates=sorted(candidates); print(candidates[0] if candidates else '')"`) do set "LOGIN_PATH=%%U"
if not defined LOGIN_PATH (
    set "ERROR_MESSAGE=Login endpoint not found in OpenAPI spec."
    set "ERROR_URL=%DIRECT_BASE%/api/v1/auth/openapi.json"
    set "ERROR_STATUS="
    goto :emit_error_json
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
    set "ERROR_MESSAGE=Login endpoint returned 404 on gateway and direct."
    set "ERROR_URL=%DIRECT_URL%"
    set "ERROR_EMAIL=%ADMIN_EMAIL%"
    set "ERROR_STATUS=404"
    set "ERROR_BODY_FILE=%BODY_FILE%"
    goto :emit_error_json
)
if not "%REQUEST_RESULT%"=="0" (
    goto :emit_error_json
)

endlocal & echo %TOKEN%

exit /b 0

:emit_error_json
python -c "import json, os; from pathlib import Path; max_len=int(os.environ.get('MAX_BODY_CHARS','1000')); body_file=os.environ.get('ERROR_BODY_FILE') or ''; body_excerpt=''; \
path=Path(body_file) if body_file else None; \
body_excerpt=path.read_text(encoding='utf-8',errors='ignore')[:max_len] if path and path.exists() else ''; \
data={ \
    'message': os.environ.get('ERROR_MESSAGE'), \
    'url': os.environ.get('ERROR_URL'), \
    'status': os.environ.get('ERROR_STATUS'), \
    'email': os.environ.get('ERROR_EMAIL'), \
    'login_path': os.environ.get('ERROR_LOGIN_PATH'), \
    'gateway_url': os.environ.get('ERROR_GATEWAY_URL'), \
    'direct_url': os.environ.get('ERROR_DIRECT_URL'), \
    'body_excerpt': body_excerpt or None \
}; \
print(json.dumps(data, ensure_ascii=False))" 1>&2
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

for /f "usebackq delims=" %%T in (`python -c "import json;from pathlib import Path; p=Path(r'%BODY_FILE%'); data=json.loads(p.read_text(encoding='utf-8',errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN=%%T"
if not "%TOKEN%"=="" exit /b 0
if "%STATUS%"=="404" exit /b 2
set "ERROR_MESSAGE=Admin token request failed."
set "ERROR_URL=%LOGIN_URL%"
set "ERROR_EMAIL=%ADMIN_EMAIL%"
set "ERROR_STATUS=%STATUS%"
set "ERROR_BODY_FILE=%BODY_FILE%"
exit /b 1

exit /b 0
