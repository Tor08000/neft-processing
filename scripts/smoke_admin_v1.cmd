@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_NAME=smoke_admin_v1"
if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "usebackq delims=" %%I in (`python -c "from datetime import datetime; print(datetime.now().strftime('%%Y-%%m-%%d_%%H%%M'))"`) do set "ts=%%I"
set "LOG_FILE=%LOG_DIR%\\smoke_admin_v1_%ts%.log"

echo %SCRIPT_NAME% started at %date% %time% > "%LOG_FILE%"

call :log "[1/8] admin token"
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 goto fail
if "%TOKEN%"=="" goto fail
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :log "[2/8] admin verify"
call :curl_check "%CORE_URL%/v1/admin/auth/verify" "admin_verify.txt" "204"
if errorlevel 1 goto fail

call :log "[3/8] admin me"
call :curl_check "%CORE_URL%/v1/admin/me" "admin_me.json" "200"
if errorlevel 1 goto fail

call :log "[4/8] admin runtime summary"
call :curl_check "%CORE_URL%/v1/admin/runtime/summary" "admin_runtime_summary.json" "200"
if errorlevel 1 goto fail

call :log "[5/8] admin ops summary"
call :curl_check "%CORE_URL%/v1/admin/ops/summary" "admin_ops_summary.json" "200"
if errorlevel 1 goto fail

call :log "[6/8] admin finance overview"
call :curl_check "%CORE_URL%/v1/admin/finance/overview?window=24h" "admin_finance_overview.json" "200"
if errorlevel 1 goto fail

call :log "[7/8] admin legal partners"
call :curl_check "%CORE_URL%/v1/admin/legal/partners" "admin_legal_partners.json" "200"
if errorlevel 1 goto fail

call :log "[8/8] admin audit feed"
call :curl_check "%CORE_URL%/v1/admin/audit" "admin_audit.json" "200"
if errorlevel 1 goto fail

echo PASS >> "%LOG_FILE%"
echo PASS
exit /b 0

:fail
echo FAIL >> "%LOG_FILE%"
echo FAIL
exit /b 1

:curl_check
set "URL=%~1"
set "OUT=%~2"
set "ALLOWED=%~3"
set "CODE="

curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\\admin_v1_status.code" 2>> "%LOG_FILE%"
set /p CODE=<"%TEMP%\\admin_v1_status.code"
if "%CODE%"=="404" (
  call :log "FAIL: admin v1 router not wired"
  echo FAIL: admin v1 router not wired
  exit /b 2
)
if "%CODE%"=="%ALLOWED%" exit /b 0
exit /b 1

:log
>> "%LOG_FILE%" echo %~1
exit /b 0
