@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%NEFT_BOOTSTRAP_CLIENT_EMAIL%"=="" (
  set "CLIENT_EMAIL=client@neft.local"
) else (
  set "CLIENT_EMAIL=%NEFT_BOOTSTRAP_CLIENT_EMAIL%"
)
if "%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"=="" (
  set "CLIENT_PASSWORD=Client123!"
) else (
  set "CLIENT_PASSWORD=%NEFT_BOOTSTRAP_CLIENT_PASSWORD%"
)

set "LOGIN_FILE=%TEMP%\client_bootstrap_login_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\client_bootstrap_status_%RANDOM%.txt"

curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%CLIENT_EMAIL%\",\"password\":\"%CLIENT_PASSWORD%\",\"portal\":\"client\"}" "%GATEWAY_BASE%%AUTH_BASE%/login" > "%STATUS_FILE%"
set /p LOGIN_STATUS=<"%STATUS_FILE%"
if not "%LOGIN_STATUS%"=="200" (
  echo [FAIL] client login HTTP %LOGIN_STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] client login missing access_token
  exit /b 1
)

call :check_json_auth_portal "client auth/me" "%GATEWAY_BASE%%AUTH_BASE%/me" "%CLIENT_TOKEN%" "client" || exit /b 1
call :check_json_auth "client core portal/me" "%GATEWAY_BASE%%CORE_BASE%/portal/me" "%CLIENT_TOKEN%" || exit /b 1

echo [PASS] client bootstrap OK
exit /b 0

:check_json
set "LABEL=%~1"
set "URL=%~2"
set "HEADERS=%~3"
set "RESP_FILE=%TEMP%\client_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\client_bootstrap_resp_status_%RANDOM%.txt"

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

:check_json_auth
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "RESP_FILE=%TEMP%\client_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\client_bootstrap_resp_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%URL%" > "%RESP_STATUS_FILE%"
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

:check_json_auth_portal
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "PORTAL=%~4"
set "RESP_FILE=%TEMP%\client_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\client_bootstrap_resp_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" -H "X-Portal: %PORTAL%" "%URL%" > "%RESP_STATUS_FILE%"
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
