@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

set "LOGIN_BODY_FILE=%TEMP%\admin_login_body_%RANDOM%.json"
set "LOGIN_RESP_FILE=%TEMP%\admin_login_%RANDOM%.json"

python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal': 'admin'}), encoding='utf-8')"
call :http_request "POST" "%GATEWAY_BASE%%AUTH_BASE%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_RESP_FILE%" || goto :fail

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%T"
if "%ADMIN_TOKEN%"=="" goto :fail

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

call :http_request "GET" "%GATEWAY_BASE%%CORE_BASE%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%TEMP%\admin_verify_%RANDOM%.json" || goto :fail

call :http_request "GET" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/me" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_me_%RANDOM%.json" || goto :fail
call :http_request "GET" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/runtime/summary" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_runtime_%RANDOM%.json" || goto :fail
call :http_request "GET" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/finance/overview?window=24h" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_finance_%RANDOM%.json" || goto :fail
call :http_request "GET" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/legal/partners?limit=50&offset=0" "%ADMIN_AUTH_HEADER%" "" "200" "%TEMP%\admin_legal_%RANDOM%.json" || goto :fail

echo ADMIN_V1: PASS
exit /b 0

:fail
echo ADMIN_V1: FAIL
exit /b 1

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\admin_v1_resp_%RANDOM%.json"
if "%BODY_FILE%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq delims=" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq delims=" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq delims=" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq delims=" %%c in (`curl -sS -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
)
if "%CODE%"=="" exit /b 1
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if not defined MATCHED exit /b 1
if "%CODE%"=="200" (
  python -c "import json; from pathlib import Path; json.loads(Path(r'%OUT%').read_text(encoding='utf-8', errors='ignore') or '{}')" >NUL 2>&1
  if errorlevel 1 exit /b 1
)
exit /b 0
