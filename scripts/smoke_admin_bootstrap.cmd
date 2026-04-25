@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%CORE_ADMIN_VERIFY%"=="" set "CORE_ADMIN_VERIFY=%CORE_BASE%/admin/auth/verify"

if "%NEFT_BOOTSTRAP_ADMIN_EMAIL%"=="" (
  set "ADMIN_EMAIL=admin@neft.local"
) else (
  set "ADMIN_EMAIL=%NEFT_BOOTSTRAP_ADMIN_EMAIL%"
)
if "%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"=="" (
  set "ADMIN_PASSWORD=Neft123!"
) else (
  set "ADMIN_PASSWORD=%NEFT_BOOTSTRAP_ADMIN_PASSWORD%"
)

set "LOGIN_FILE=%TEMP%\admin_bootstrap_login_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\admin_bootstrap_status_%RANDOM%.txt"

curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\",\"portal\":\"admin\"}" "%GATEWAY_BASE%%AUTH_BASE%/login" > "%STATUS_FILE%"
set /p LOGIN_STATUS=<"%STATUS_FILE%"
if not "%LOGIN_STATUS%"=="200" (
  echo [FAIL] admin login HTTP %LOGIN_STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%T"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  exit /b 1
)

call :check_status_auth "admin auth verify" "%GATEWAY_BASE%%CORE_ADMIN_VERIFY%" "%ADMIN_TOKEN%" "204" || exit /b 1
call :check_json_auth "admin core v1/admin/me" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/me" "%ADMIN_TOKEN%" || exit /b 1

echo [PASS] admin bootstrap OK
exit /b 0

:check_json
set "LABEL=%~1"
set "URL=%~2"
set "HEADERS=%~3"
set "RESP_FILE=%TEMP%\admin_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\admin_bootstrap_resp_status_%RANDOM%.txt"

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
set "RESP_FILE=%TEMP%\admin_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\admin_bootstrap_resp_status_%RANDOM%.txt"

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
set "RESP_FILE=%TEMP%\admin_bootstrap_resp_%RANDOM%.json"
set "RESP_STATUS_FILE=%TEMP%\admin_bootstrap_resp_status_%RANDOM%.txt"

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

:check_status_auth
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "EXPECTED=%~4"
set "RESP_FILE=%TEMP%\admin_bootstrap_resp_%RANDOM%.txt"
set "RESP_STATUS_FILE=%TEMP%\admin_bootstrap_resp_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="%EXPECTED%" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  type "%RESP_FILE%"
  exit /b 1
)

echo [PASS] %LABEL%
exit /b 0
