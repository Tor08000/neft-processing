@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "ENV_FILE=.env"
if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
set "LOGIN_URL=%AUTH_HOST_BASE%%AUTH_BASE%/login"

if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        if /I "%%A"=="NEFT_BOOTSTRAP_ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="NEFT_BOOTSTRAP_ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
        if /I "%%A"=="ADMIN_EMAIL" set "ADMIN_EMAIL=%%B"
        if /I "%%A"=="ADMIN_PASSWORD" set "ADMIN_PASSWORD=%%B"
    )
)

set "BODY_FILE=%TEMP%\auth_body.json"
set "REQUEST_BODY_FILE=%TEMP%\auth_body_request_%RANDOM%.json"
set "STATUS="
set "TOKEN="

python -c "import json; from pathlib import Path; Path(r'%REQUEST_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%', 'password': r'%ADMIN_PASSWORD%', 'portal': 'admin'}), encoding='utf-8')"
for /f "usebackq tokens=*" %%c in (`curl -sS -o "%BODY_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%REQUEST_BODY_FILE%" "%LOGIN_URL%" 2^>nul`) do set "STATUS=%%c"

for /f "usebackq tokens=*" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%BODY_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN=%%T"

if not "%TOKEN%"=="" goto :emit_token
if not "%STATUS%"=="200" goto :emit_error_json
if "%TOKEN%"=="" goto :emit_error_json

:emit_token
echo %TOKEN%
del /q "%REQUEST_BODY_FILE%" 2>nul
exit /b 0

:emit_error_json
python -c "import json, os; from pathlib import Path; body=Path(r'%BODY_FILE%').read_text(encoding='utf-8', errors='ignore') if Path(r'%BODY_FILE%').exists() else ''; print(json.dumps({'message': 'Admin token request failed.', 'url': r'%LOGIN_URL%', 'status': os.environ.get('STATUS'), 'email': r'%ADMIN_EMAIL%', 'body_excerpt': body[:1000] or None}, ensure_ascii=False))" 1>&2
del /q "%REQUEST_BODY_FILE%" 2>nul
exit /b 1
