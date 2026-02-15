@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@example.com"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"

set "TMP_DIR=%TEMP%"
set "LOGIN_OUT=%TMP_DIR%\client_logistics_login.json"
set "STATUS_FILE=%TMP_DIR%\client_logistics_status_%RANDOM%.txt"

if "%CLIENT_TOKEN%"=="" (
  set "PAYLOAD_FILE=%TMP_DIR%\client_logistics_login_payload_%RANDOM%.json"
  > "%PAYLOAD_FILE%" echo {"email":"%CLIENT_EMAIL%","password":"%CLIENT_PASSWORD%","portal":"client"}
  curl -sS -o "%LOGIN_OUT%" -w "%%{http_code}" -H "Content-Type: application/json" -X POST "%GATEWAY_BASE%%AUTH_BASE%/login" -d @"%PAYLOAD_FILE%" > "%STATUS_FILE%"
  set /p STATUS=<"%STATUS_FILE%"
  if not "%STATUS%"=="200" (
    echo [FAIL] login HTTP %STATUS%
    type "%LOGIN_OUT%"
    exit /b 1
  )

  for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_OUT%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"
)

if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] missing CLIENT_TOKEN
  exit /b 1
)

call :check "fleet" "%GATEWAY_BASE%%CORE_BASE%/client/logistics/fleet"
if errorlevel 1 exit /b 1
call :check "trips" "%GATEWAY_BASE%%CORE_BASE%/client/logistics/trips"
if errorlevel 1 exit /b 1
call :check "fuel" "%GATEWAY_BASE%%CORE_BASE%/client/logistics/fuel"
if errorlevel 1 exit /b 1

echo [PASS] smoke_client_logistics OK
exit /b 0

:check
set "LABEL=%~1"
set "URL=%~2"
set "OUT_FILE=%TMP_DIR%\client_logistics_%LABEL%.json"
set "STATUS_FILE=%TMP_DIR%\client_logistics_status_%RANDOM%.txt"
curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %CLIENT_TOKEN%" "%URL%" > "%STATUS_FILE%"
set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %STATUS%
  type "%OUT_FILE%"
  exit /b 1
)
echo [PASS] %LABEL% HTTP 200
exit /b 0
