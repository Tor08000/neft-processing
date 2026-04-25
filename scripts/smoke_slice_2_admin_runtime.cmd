@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

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

call :login admin "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "admin" || exit /b 1

call :fetch_html "admin SPA" "%GATEWAY_BASE%/admin/" "admin_index_slice2.html" || exit /b 1
call :assert_contains "admin asset references" "%TEMP%\admin_index_slice2.html" "/admin/assets/" || exit /b 1

call set "ADMIN_TOKEN=%%admin_TOKEN%%"
call :fetch_json_auth "admin v1/admin/me" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/me" "%ADMIN_TOKEN%" "admin_me_slice2.json" || exit /b 1
call :fetch_json_auth "admin runtime summary" "%GATEWAY_BASE%%CORE_BASE%/v1/admin/runtime/summary" "%ADMIN_TOKEN%" "admin_runtime_summary.json" || exit /b 1
set "RUNTIME_SUMMARY_FILE=%TEMP%\admin_runtime_summary.json"

python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RUNTIME_SUMMARY_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); health=data.get('health') or {}; queues=data.get('queues') or {}; settlement=queues.get('settlement') or {}; payout=queues.get('payout') or {}; warnings=data.get('warnings') or []; required=['core_api','auth_host','gateway','integration_hub','ai_service','prometheus','grafana','loki','otel_collector']; missing=[key for key in required if key not in health]; print('[runtime] env=' + str(data.get('environment')) + ' read_only=' + str(data.get('read_only'))); print('[runtime] core_api=' + str(health.get('core_api')) + ' auth_host=' + str(health.get('auth_host')) + ' gateway=' + str(health.get('gateway')) + ' integration_hub=' + str(health.get('integration_hub')) + ' ai_service=' + str(health.get('ai_service'))); print('[runtime] prometheus=' + str(health.get('prometheus')) + ' grafana=' + str(health.get('grafana')) + ' loki=' + str(health.get('loki')) + ' otel_collector=' + str(health.get('otel_collector'))); print('[runtime] settlement_depth=' + str(settlement.get('depth')) + ' payout_depth=' + str(payout.get('depth')) + ' warnings=' + str(len(warnings))); raise SystemExit(1 if missing else 0)" || exit /b 1

echo [PASS] slice 2 admin runtime OK
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
call set "LOGIN_TOKEN=%%%LABEL%_TOKEN%%"
if "%LOGIN_TOKEN%"=="" (
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
set "RESP_STATUS_FILE=%TEMP%\slice2_resp_status_%RANDOM%.txt"

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

:fetch_json_auth
set "LABEL=%~1"
set "URL=%~2"
set "TOKEN=%~3"
set "FILE_NAME=%~4"
set "RESP_FILE=%TEMP%\%FILE_NAME%"
set "RESP_STATUS_FILE=%TEMP%\slice2_auth_resp_status_%RANDOM%.txt"

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

:fetch_head
set "LABEL=%~1"
set "URL=%~2"
set "RESP_STATUS_FILE=%TEMP%\slice2_head_status_%RANDOM%.txt"

curl -sS -o NUL -I -w "%%{http_code}" "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  exit /b 1
)

echo [PASS] %LABEL%
exit /b 0

:fetch_html
set "LABEL=%~1"
set "URL=%~2"
set "FILE_NAME=%~3"
set "RESP_FILE=%TEMP%\%FILE_NAME%"
set "RESP_STATUS_FILE=%TEMP%\slice2_html_status_%RANDOM%.txt"

curl -sS -o "%RESP_FILE%" -w "%%{http_code}" "%URL%" > "%RESP_STATUS_FILE%"
set /p RESP_STATUS=<"%RESP_STATUS_FILE%"
if not "%RESP_STATUS%"=="200" (
  echo [FAIL] %LABEL% HTTP %RESP_STATUS%
  exit /b 1
)

echo [PASS] %LABEL%
exit /b 0

:assert_contains
set "LABEL=%~1"
set "FILE_PATH=%~2"
set "NEEDLE=%~3"

python -c "from pathlib import Path; data=Path(r'%FILE_PATH%').read_text(encoding='utf-8', errors='ignore'); raise SystemExit(0 if r'%NEEDLE%' in data else 1)" || (
  echo [FAIL] %LABEL%
  exit /b 1
)

echo [PASS] %LABEL%
exit /b 0
