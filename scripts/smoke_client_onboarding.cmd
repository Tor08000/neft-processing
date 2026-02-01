@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=client"

set "LOGIN_BODY_FILE=%TEMP%\client_login_body_%RANDOM%.json"
set "LOGIN_RESP_FILE=%TEMP%\client_login_%RANDOM%.json"

python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%','password': r'%CLIENT_PASSWORD%','portal': 'client'}), encoding='utf-8')"
call :http_request "POST" "%GATEWAY_BASE%%AUTH_BASE%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_RESP_FILE%" || goto :fail

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"
if "%CLIENT_TOKEN%"=="" goto :fail

set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

set "PROFILE_BODY_FILE=%TEMP%\client_profile_body_%RANDOM%.json"
set "PROFILE_RESP_FILE=%TEMP%\client_profile_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PROFILE_BODY_FILE%').write_text(json.dumps({'org_type': 'LEGAL','name': 'ООО ТЕСТ','inn': '7707083893'}), encoding='utf-8')"
call :http_request "POST" "%GATEWAY_BASE%%CORE_BASE%/client/onboarding/profile" "%CLIENT_AUTH_HEADER%" "%PROFILE_BODY_FILE%" "200" "%PROFILE_RESP_FILE%" || goto :fail

set "PORTAL_RESP_FILE=%TEMP%\client_portal_me_%RANDOM%.json"
call :http_request "GET" "%GATEWAY_BASE%%CORE_BASE%/portal/me" "%CLIENT_AUTH_HEADER%" "" "200" "%PORTAL_RESP_FILE%" || goto :fail

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=data.get('org') is not None; print('ok' if ok else 'fail')"`) do set "CHECK_ORG=%%T"
if /i not "%CHECK_ORG%"=="ok" goto :fail

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('org',{}).get('status',''))"`) do set "ORG_STATUS=%%T"
if /i not "%ORG_STATUS%"=="ONBOARDING" goto :fail

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles=[r for r in data.get('roles') or []]; print('ok' if 'CLIENT_OWNER' in roles else 'fail')"`) do set "ROLE_OK=%%T"
if /i not "%ROLE_OK%"=="ok" goto :fail

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); org_id=(data.get('org') or {}).get('id'); ent_id=(data.get('entitlements_snapshot') or {}).get('org_id'); print('ok' if org_id and ent_id and str(org_id)==str(ent_id) else 'fail')"`) do set "ENT_OK=%%T"
if /i not "%ENT_OK%"=="ok" goto :fail

echo CLIENT_ONBOARDING: PASS
exit /b 0

:fail
echo CLIENT_ONBOARDING: FAIL
exit /b 1

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\client_onboarding_resp_%RANDOM%.json"
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
