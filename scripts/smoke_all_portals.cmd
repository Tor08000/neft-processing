@echo off
setlocal EnableExtensions EnableDelayedExpansion

for /f "delims=" %%e in ('echo prompt $E^| cmd') do set "ESC=%%e"
set "GREEN=%ESC%[32m"
set "RED=%ESC%[31m"
set "YELLOW=%ESC%[33m"
set "RESET=%ESC%[0m"

set "OK=%GREEN%OK%RESET%"
set "FAIL=%RED%FAIL%RESET%"

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"

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

set "FAILED=0"

call :check_portal client || set "FAILED=1"
call :check_portal partner || set "FAILED=1"
call :check_portal admin || set "FAILED=1"

call :login_portal client "%CLIENT_EMAIL%" "%CLIENT_PASSWORD%" CLIENT_TOKEN || set "FAILED=1"
call :login_portal partner "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" PARTNER_TOKEN || set "FAILED=1"
call :login_portal admin "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" ADMIN_TOKEN || set "FAILED=1"

if "%CLIENT_TOKEN%"=="" set "FAILED=1"
if "%PARTNER_TOKEN%"=="" set "FAILED=1"
if "%ADMIN_TOKEN%"=="" set "FAILED=1"

if "%FAILED%"=="1" goto finalize

call :check_json "client portal/me" "%CORE_URL%/portal/me" "Authorization: Bearer %CLIENT_TOKEN%" || set "FAILED=1"
call :check_json "client dashboard" "%CORE_URL%/portal/client/dashboard" "Authorization: Bearer %CLIENT_TOKEN%" || set "FAILED=1"

call :check_json "partner portal/me" "%CORE_URL%/portal/me" "Authorization: Bearer %PARTNER_TOKEN%" || set "FAILED=1"
call :check_json "partner ledger" "%CORE_URL%/partner/ledger?limit=10" "Authorization: Bearer %PARTNER_TOKEN%" || set "FAILED=1"

call :check_json "admin v1/admin/me" "%CORE_URL%/v1/admin/me" "Authorization: Bearer %ADMIN_TOKEN%" || set "FAILED=1"
call :check_json "admin runtime summary" "%CORE_URL%/admin/runtime/summary" "Authorization: Bearer %ADMIN_TOKEN%" || set "FAILED=1"
call :print_runtime_summary "%LAST_JSON%" || set "FAILED=1"

goto finalize

:check_portal
set "PORTAL=%~1"
set "INDEX_FILE=%TEMP%\%PORTAL%_index_%RANDOM%.html"
set "STATUS_FILE=%TEMP%\%PORTAL%_status_%RANDOM%.txt"

curl -sS -o "%INDEX_FILE%" -w "%%{http_code}" "%GATEWAY_BASE%/%PORTAL%/" > "%STATUS_FILE%"
if errorlevel 1 (
  echo [%PORTAL%] Failed to download index.
  exit /b 1
)

set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [%PORTAL%] Unexpected status for index: %STATUS%
  type "%INDEX_FILE%"
  exit /b 1
)

echo [%OK%] %PORTAL% index

for /f "usebackq delims=" %%A in (`python -c "import re; from pathlib import Path; data=Path(r'%INDEX_FILE%').read_text(encoding='utf-8',errors='ignore'); assets=re.findall(r'/%PORTAL%/assets/[^\"\']+\.(?:js|mjs|css)', data); seen=set(); [print(a) for a in assets if not (a in seen or seen.add(a))]"`) do (
  call :check_asset "%PORTAL%" "%%A" || exit /b 1
)

exit /b 0

:check_asset
set "PORTAL=%~1"
set "ASSET=%~2"
set "EXPECT=application/javascript"
if /I "%ASSET:~-4%"==".css" set "EXPECT=text/css"

set "HEADER_FILE=%TEMP%\asset_header_%RANDOM%.txt"

curl -sS -I "%GATEWAY_BASE%%ASSET%" > "%HEADER_FILE%"
if errorlevel 1 (
  echo [%PORTAL%] Failed to fetch headers for %ASSET%
  exit /b 1
)

findstr /R /I "HTTP/.* 200" "%HEADER_FILE%" >nul || (
  echo [%PORTAL%] Unexpected status for %ASSET%
  type "%HEADER_FILE%"
  exit /b 1
)

findstr /R /I "Content-Type: .*%EXPECT%" "%HEADER_FILE%" >nul || (
  echo [%PORTAL%] Unexpected Content-Type for %ASSET% (expected %EXPECT%)
  type "%HEADER_FILE%"
  exit /b 1
)

findstr /I "text/html" "%HEADER_FILE%" >nul && (
  echo [%PORTAL%] HTML response detected for %ASSET%
  exit /b 1
)

echo [%OK%] %PORTAL% asset %ASSET%
exit /b 0

:login_portal
set "PORTAL=%~1"
set "EMAIL=%~2"
set "PASSWORD=%~3"
set "TOKEN_VAR=%~4"
set "LOGIN_FILE=%TEMP%\login_%PORTAL%_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\login_%PORTAL%_%RANDOM%.status"

curl -sS -o "%LOGIN_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"portal\":\"%PORTAL%\"}" "%AUTH_URL%/login" > "%STATUS_FILE%"
if errorlevel 1 (
  echo [%PORTAL%] Login request failed.
  exit /b 1
)

set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [%PORTAL%] Login returned status %STATUS%
  type "%LOGIN_FILE%"
  exit /b 1
)

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8',errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "TOKEN=%%T"
if "%TOKEN%"=="" (
  echo [%PORTAL%] No access token returned.
  exit /b 1
)

call set "%TOKEN_VAR%=%TOKEN%"

call :check_json "%PORTAL% auth/me" "%AUTH_URL%/me" "Authorization: Bearer %TOKEN%" "X-Portal: %PORTAL%" || exit /b 1

echo [%OK%] %PORTAL% login
exit /b 0

:check_json
set "LABEL=%~1"
set "URL=%~2"
set "HEADER1=%~3"
set "HEADER2=%~4"
set "OUT_FILE=%TEMP%\verify_%RANDOM%.json"
set "STATUS_FILE=%TEMP%\verify_%RANDOM%.status"

if "%HEADER2%"=="" (
  curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "%HEADER1%" "%URL%" > "%STATUS_FILE%"
) else (
  curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "%HEADER1%" -H "%HEADER2%" "%URL%" > "%STATUS_FILE%"
)

if errorlevel 1 (
  echo [%LABEL%] Request failed.
  exit /b 1
)

set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="200" (
  echo [%LABEL%] Unexpected status %STATUS%
  type "%OUT_FILE%"
  exit /b 1
)

python -c "import json; from pathlib import Path; json.loads(Path(r'%OUT_FILE%').read_text(encoding='utf-8', errors='ignore'))" >NUL 2>&1
if errorlevel 1 (
  echo [%LABEL%] Invalid JSON
  type "%OUT_FILE%"
  exit /b 1
)

set "LAST_JSON=%OUT_FILE%"

echo [%OK%] %LABEL%
exit /b 0

:print_runtime_summary
set "RESP_FILE=%~1"
if "%RESP_FILE%"=="" exit /b 0

python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESP_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); health=data.get('health') or {}; queues=data.get('queues') or {}; settlement=queues.get('settlement') or {}; payout=queues.get('payout') or {}; print('[runtime] env=' + str(data.get('environment')) + ' read_only=' + str(data.get('read_only'))); print('[runtime] core_api=' + str(health.get('core_api')) + ' auth_host=' + str(health.get('auth_host')) + ' gateway=' + str(health.get('gateway'))); print('[runtime] settlement_depth=' + str(settlement.get('depth')) + ' payout_depth=' + str(payout.get('depth')))" || exit /b 1

exit /b 0

:finalize
if "%FAILED%"=="0" (
  echo %OK% smoke_all_portals.cmd finished successfully
  exit /b 0
)

echo %FAIL% smoke_all_portals.cmd finished with failures
exit /b 1
