@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "usebackq delims=" %%I in (`python -c "from datetime import datetime; print(datetime.now().strftime('%%Y-%%m-%%d_%%H%%M'))"`) do set "ts=%%I"
set "LOG_FILE=%LOG_DIR%\\smoke_admin_finance_%ts%.log"

echo smoke_admin_finance.cmd started at %date% %time% > "%LOG_FILE%"

call :log "[1/7] admin token"
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 goto fail
if "%TOKEN%"=="" goto fail
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :log "[2/7] admin me"
call :curl_check "%CORE_URL%/v1/admin/me" "admin_me.json" "200"
if errorlevel 1 goto fail

call :log "[3/7] finance overview"
call :curl_check "%CORE_URL%/v1/admin/finance/overview?window=24h" "finance_overview.json" "200"
if errorlevel 1 goto fail
findstr /C:"\"overdue_orgs\"" "finance_overview.json" >nul
if errorlevel 1 goto fail
findstr /C:"\"payment_intakes_pending\"" "finance_overview.json" >nul
if errorlevel 1 goto fail

call :log "[4/7] finance invoices"
call :curl_check "%CORE_URL%/v1/admin/finance/invoices" "finance_invoices.json" "200"
if errorlevel 1 goto fail

call :log "[5/7] finance payment intakes"
call :curl_check "%CORE_URL%/v1/admin/finance/payment-intakes" "finance_intakes.json" "200"
if errorlevel 1 goto fail

call :log "[6/7] reconciliation imports"
call :curl_check "%CORE_URL%/v1/admin/reconciliation/imports" "reconciliation_imports.json" "200"
if errorlevel 1 goto fail

call :log "[7/7] payout queue"
call :curl_check "%CORE_URL%/v1/admin/finance/payouts" "finance_payouts.json" "200"
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

curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\\finance_status.code" 2>> "%LOG_FILE%"
set /p CODE=<"%TEMP%\\finance_status.code"
if "%CODE%"=="%ALLOWED%" exit /b 0
exit /b 1

:log
>> "%LOG_FILE%" echo %~1
exit /b 0
