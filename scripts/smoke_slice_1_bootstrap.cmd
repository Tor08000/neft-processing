@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%NEFT_BOOTSTRAP_CLIENT_EMAIL%"=="" (
  set "CLIENT_EMAIL=client@neft.local"
) else (
  set "CLIENT_EMAIL=%NEFT_BOOTSTRAP_CLIENT_EMAIL%"
)
if "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"=="" (
  set "CLIENT_PASSWORD=client"
) else (
  set "CLIENT_PASSWORD=%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"
)

if "%NEFT_BOOTSTRAP_PARTNER_EMAIL%"=="" (
  set "PARTNER_EMAIL=partner@neft.local"
) else (
  set "PARTNER_EMAIL=%NEFT_BOOTSTRAP_PARTNER_EMAIL%"
)
if "%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"=="" (
  set "PARTNER_PASSWORD=partner"
) else (
  set "PARTNER_PASSWORD=%NEFT_BOOTSTRAP_PARTNER_PASSWORD%"
)

if "%NEFT_BOOTSTRAP_ADMIN_EMAIL%"=="" (
  set "ADMIN_EMAIL=admin@example.com"
) else (
  set "ADMIN_EMAIL=%NEFT_BOOTSTRAP_ADMIN_EMAIL%"
)
if "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"=="" (
  set "ADMIN_PASSWORD=admin"
) else (
  set "ADMIN_PASSWORD=%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"
)

call :login portal_client "%CLIENT_EMAIL%" "%CLIENT_PASSWORD%" "client" || exit /b 1
call :login portal_partner "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" "partner" || exit /b 1
call :login admin "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "" || exit /b 1

call :fetch_json "client portal/me" "%GATEWAY_BASE%%CORE_BASE%/portal/me" "-H \"Authorization: Bearer %portal_client_TOKEN%\"" "client_portal_me.json" || exit /b 1
call :fetch_json "partner portal/me" "%GATEWAY_BASE%%CORE_BASE%/portal/me" "-H \"Authorization: Bearer %portal_partner_TOKEN%\"" "partner_portal_me.json" || exit /b 1
call :fetch_json "admin v1/admin/me" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/me" "-H \"Authorization: Bearer %admin_TOKEN%\"" "admin_me.json" || exit /b 1

call :print_portal_summary "client" "%TEMP%\client_portal_me.json" || exit /b 1
call :print_portal_summary "partner" "%TEMP%\partner_portal_me.json" || exit /b 1
call :print_admin_summary "%TEMP%\admin_me.json" || exit /b 1

echo [PASS] slice 1 bootstrap OK
exit /b 0

:login
set "LABEL=%~1"
set "EMAIL=%~2"
set "PASSWORD=%~3"
set "PORTAL=%~4"
set "LOGIN_FILE=%TEMP%\%LABEL%_login_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\%LABEL%_login_status_%RANDOM%.txt"

if "%PORTAL%"=="" (
  set "LOGIN_PAYLOAD={\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\"}"
) else (
  set "LOGIN_PAYLOAD={\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"portal\":\"%PORTAL%\"}"
)
curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "%LOGIN_PAYLOAD%" "%GATEWAY_BASE%%AUTH_BASE%/login" > "%STATUS_FILE%"
set /p LOGIN_STATUS=<"%STATUS_FILE%"
if not "%LOGIN_STATUS%"=="200" (
  echo [FAIL] %LABEL% login HTTP %LOGIN_STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "%LABEL%_TOKEN=%%T"
if "!%LABEL%_TOKEN!"=="" (
  echo [FAIL] %LABEL% login missing access_token
  exit /b 1
)

echo [PASS] %LABEL% login OK
exit /b 0

:fetch_json
set "LABEL=%~1"
set "URL=%~2"
set "HEADERS=%~3"
set "FILE_NAME=%~4"
set "RESP_FILE=%TEMP%\%FILE_NAME%"
set "RESP_STATUS_FILE=%TEMP%\slice1_resp_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" %HEADERS% "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  type "%RESP_FILE%"
  exit /b 1
)
python -c "import json; from pathlib import Path; json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore'))" >NUL 2>&1
if errorlevel 1 (
  echo [FAIL] %LABEL% invalid JSON
  type "%RESP_FILE%"
  exit /b 1
)

echo [PASS] %LABEL%
exit /b 0

:print_portal_summary
set "LABEL=%~1"
set "RESP_FILE=%~2"
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles=data.get('roles') or data.get('user_roles') or []; access_state=data.get('access_state'); print('[%LABEL%] access_state=' + str(access_state) + ' roles=' + str(roles))" || exit /b 1
exit /b 0

:print_admin_summary
set "RESP_FILE=%~1"
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles=data.get('roles') or (data.get('admin_user') or {}).get('roles') or []; read_only=data.get('read_only'); print(f'[admin] roles={roles} read_only={read_only}')" || exit /b 1
exit /b 0
