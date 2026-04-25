@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%API_URL%"=="" set "API_URL=http://localhost"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"

set "LOGIN_BODY_FILE=%TEMP%\portal_access_login_body_%RANDOM%.json"
set "LOGIN_RESP_FILE=%TEMP%\portal_access_login_%RANDOM%.json"
set "RESPONSE_FILE=%TEMP%\portal_access_me_%RANDOM%.json"
set "TOKEN="
set "LOGIN_STATUS="
set "PORTAL_STATUS="

python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%','password': r'%CLIENT_PASSWORD%','portal':'client'}), encoding='utf-8')"
for /f "usebackq delims=" %%A in (`curl -sS -o "%LOGIN_RESP_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%LOGIN_BODY_FILE%" "%API_URL%/api/v1/auth/login" 2^>nul`) do set "LOGIN_STATUS=%%A"
if not "%LOGIN_STATUS%"=="200" (
  echo login status: %LOGIN_STATUS%
  if exist "%LOGIN_RESP_FILE%" type "%LOGIN_RESP_FILE%"
  goto :fail
)

for /f "usebackq delims=" %%A in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN=%%A"
if "%TOKEN%"=="" (
  echo Failed to get client token.
  goto :fail
)

for /f "usebackq delims=" %%A in (`curl -sS -o "%RESPONSE_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%API_URL%/api/core/portal/me" 2^>nul`) do set "PORTAL_STATUS=%%A"
if not "%PORTAL_STATUS%"=="200" (
  echo portal/me status: %PORTAL_STATUS%
  if exist "%RESPONSE_FILE%" type "%RESPONSE_FILE%"
  goto :fail
)

python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESPONSE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print('access_state: ' + str(data.get('access_state') or '')); reason=data.get('access_reason'); print('access_reason: ' + str(reason)) if reason else None"
echo PORTAL_ACCESS_STATE: PASS
goto :cleanup_success

:fail
del /q "%LOGIN_BODY_FILE%" 2>nul
del /q "%LOGIN_RESP_FILE%" 2>nul
del /q "%RESPONSE_FILE%" 2>nul
exit /b 1

:cleanup_success
del /q "%LOGIN_BODY_FILE%" 2>nul
del /q "%LOGIN_RESP_FILE%" 2>nul
del /q "%RESPONSE_FILE%" 2>nul
exit /b 0
