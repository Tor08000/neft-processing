@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"
set "AUTH_URL=%BASE_URL%/api/auth/api/v1/auth"
set "CORE_URL=%BASE_URL%/api/core/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

set "TOKEN="
set "AUTH_HEADER="
set "INVOICE_ID="

echo [1/10] Login to auth-host...
curl -s -S -X POST "%AUTH_URL%/login" -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}" > login.json
for /f "usebackq tokens=*" %%t in (`python -c "import json,sys; print(json.load(open('login.json')).get('access_token',''))"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned.
  goto :fail
)
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

call :check_get "[2/10] /auth/me" "%AUTH_URL%/me" "%AUTH_HEADER%" "200" || goto :fail
call :check_get "[3/10] Billing periods" "%CORE_URL%/billing/periods" "%AUTH_HEADER%" "200" || goto :fail

set "RUN_BODY={\"period_type\":\"ADHOC\",\"start_at\":\"2024-01-01T00:00:00Z\",\"end_at\":\"2024-01-01T01:00:00Z\",\"tz\":\"UTC\"}"
call :post_step "[4/10] Billing run (ADHOC)" "%CORE_URL%/billing/run" "!RUN_BODY!" "%AUTH_HEADER%" "200" "" || goto :fail

call :post_step "[5/10] Clearing run" "%CORE_URL%/clearing/run?date=2024-01-02" "" "%AUTH_HEADER%" "200" "202" || goto :fail

echo [6/10] List invoices (grab first id)...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoices.json "%CORE_URL%/billing/invoices?limit=1&offset=0"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Invoices list returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json,sys; data=json.load(open('invoices.json')); items=data.get('items') or []; print(items[0]['id'] if items else '')"`) do set "INVOICE_ID=%%i"
if "%INVOICE_ID%"=="" (
  echo [SKIP] No invoices yet, skipping PDF step.
) else (
  call :post_step "[7/10] Invoice PDF enqueue" "%CORE_URL%/billing/invoices/%INVOICE_ID%/pdf" "" "%AUTH_HEADER%" "200" "202" || goto :fail
)

echo [8/10] Finance payment (best-effort)...
set "PAYMENT_BODY={\"client_id\":\"demo-client\",\"amount\":1,\"currency\":\"RUB\",\"occurred_at\":\"2024-01-02T00:00:00Z\",\"external_ref\":\"smoke\"}"
call :post_step "[8/10] Finance payment" "%CORE_URL%/finance/payments" "!PAYMENT_BODY!" "%AUTH_HEADER%" "200" "201" || echo [WARN] Finance payment skipped (endpoint unavailable).

echo [9/10] Finance AR balance (best-effort)...
call :check_get "[9/10] Finance AR balance" "%CORE_URL%/finance/ar/balance?client_id=demo-client" "%AUTH_HEADER%" "200" || echo [WARN] AR balance skipped (endpoint unavailable).

call :check_get "[10/10] Clearing batches" "%CORE_URL%/clearing/batches?limit=5" "%AUTH_HEADER%" "200" || goto :fail

echo [SMOKE] Completed.
exit /b 0

:check_get
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:post_step
set "LABEL=%~1"
set "URL=%~2"
set "BODY=%~3"
set "HEADER=%~4"
set "EXPECTED=%~5"
set "ALT=%~6"
set "CODE="
if "%BODY%"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -X POST "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%"`) do set "CODE=%%c"
)
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
if not "%ALT%"=="" if "%CODE%"=="%ALT%" (
  echo [OK] %LABEL% (%CODE%)
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:fail
echo [SMOKE] Failed.
exit /b 1
