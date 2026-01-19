@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get LocalDateTime /value') do set "dt=%%I"
set "ts=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,4%"
set "LOG_FILE=%LOG_DIR%\\smoke_admin_ops_%ts%.log"

echo smoke_admin_ops.cmd started at %date% %time% > "%LOG_FILE%"

call :log "[1/4] core health"
curl -s "%CORE_URL%/health" > "%TEMP%\\ops_health.json" 2>> "%LOG_FILE%"
findstr /C:"\"status\":\"ok\"" "%TEMP%\\ops_health.json" >nul
if errorlevel 1 goto fail

call :log "[2/4] admin token"
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 goto fail
if "%TOKEN%"=="" goto fail
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :log "[3/4] admin me"
call :curl_check "%CORE_URL%/v1/admin/me" "admin_me.json" "200"
if errorlevel 1 goto fail

call :log "[4/4] ops summary"
call :curl_check "%CORE_URL%/v1/admin/ops/summary" "ops_summary.json" "200"
if errorlevel 1 goto fail

findstr /C:"\"signals\"" "ops_summary.json" >nul
if errorlevel 1 goto fail
findstr /C:"\"status\"" "ops_summary.json" >nul
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

curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\\ops_status.code" 2>> "%LOG_FILE%"
set /p CODE=<"%TEMP%\\ops_status.code"
if "%CODE%"=="%ALLOWED%" exit /b 0
exit /b 1

:log
>> "%LOG_FILE%" echo %~1
exit /b 0
