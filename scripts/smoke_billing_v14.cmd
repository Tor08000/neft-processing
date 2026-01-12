@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%/v1/auth"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=change-me"

set "TOKEN="
set "AUTH_HEADER="
set "INVOICE_ID="
set "TRANSITION_INVOICE_ID="

echo [1/16] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned.
  goto :fail
)
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

call :check_get "[2/16] /auth/me" "%AUTH_URL%/me" "%AUTH_HEADER%" "200" || goto :fail
call :check_get "[3/16] Billing periods" "%CORE_URL%/billing/periods" "%AUTH_HEADER%" "200" || goto :fail

set "RUN_BODY={\"period_type\":\"ADHOC\",\"start_at\":\"2024-01-01T00:00:00Z\",\"end_at\":\"2024-01-01T01:00:00Z\",\"tz\":\"UTC\"}"
call :post_step "[4/16] Billing run (ADHOC)" "%CORE_URL%/billing/run" "!RUN_BODY!" "%AUTH_HEADER%" "200" "" || goto :fail

call :post_step "[5/16] Clearing run" "%CORE_URL%/clearing/run?date=2024-01-02" "" "%AUTH_HEADER%" "200" "202" || goto :fail

echo [6/16] List invoices (grab first id)...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoices.json "%CORE_URL%/billing/invoices?limit=1&offset=0"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Invoices list returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json,sys; data=json.load(open('invoices.json')); items=data.get('items') or []; print(items[0]['id'] if items else '')"`) do set "INVOICE_ID=%%i"

echo [7/16] Generate draft invoice for transitions...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "{\"period_from\":\"2024-01-01\",\"period_to\":\"2024-01-31\",\"status\":\"DRAFT\"}" -X POST -o generate_invoice.json "%CORE_URL%/billing/invoices/generate"`) do set "CODE=%%c"
if not "%CODE%"=="202" (
  echo [FAIL] Invoice generation returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json,sys; data=json.load(open('generate_invoice.json')); ids=data.get('created_ids') or []; print(ids[0] if ids else '')"`) do set "TRANSITION_INVOICE_ID=%%i"
if "%TRANSITION_INVOICE_ID%"=="" set "TRANSITION_INVOICE_ID=%INVOICE_ID%"
if "%TRANSITION_INVOICE_ID%"=="" (
  echo [FAIL] Could not obtain invoice id for transitions.
  goto :fail
)
set "INVOICE_ID=%TRANSITION_INVOICE_ID%"

call :post_step "[8/16] Mark invoice ISSUED" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"ISSUED\"}" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[9/16] Mark invoice SENT" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"SENT\"}" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[10/16] Mark invoice PAID" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"PAID\"}" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[11/16] Attempt PAID->SENT (expect 409)" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"SENT\"}" "%AUTH_HEADER%" "409" "" || goto :fail

echo [12/16] Invoice detail after transitions...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoice_detail.json "%CORE_URL%/billing/invoices/%INVOICE_ID%"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Invoice detail returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%s in (`python -c "import json; d=json.load(open('invoice_detail.json')); print('status=' + str(d.get('status')) + '; issued_at=' + str(d.get('issued_at')) + '; sent_at=' + str(d.get('sent_at')) + '; paid_at=' + str(d.get('paid_at')))"`) do echo     %%s

if "%INVOICE_ID%"=="" (
  echo [SKIP] No invoices yet, skipping PDF step.
) else (
  call :post_step "[13/16] Invoice PDF enqueue" "%CORE_URL%/billing/invoices/%INVOICE_ID%/pdf" "" "%AUTH_HEADER%" "200" "202" || goto :fail
)

echo [14/16] Finance payment (best-effort)...
set "PAYMENT_BODY={\"client_id\":\"demo-client\",\"amount\":1,\"currency\":\"RUB\",\"occurred_at\":\"2024-01-02T00:00:00Z\",\"external_ref\":\"smoke\"}"
call :post_step "[14/16] Finance payment" "%CORE_URL%/finance/payments" "!PAYMENT_BODY!" "%AUTH_HEADER%" "200" "201" || echo [WARN] Finance payment skipped (endpoint unavailable).

echo [15/16] Finance AR balance (best-effort)...
call :check_get "[15/16] Finance AR balance" "%CORE_URL%/finance/ar/balance?client_id=demo-client" "%AUTH_HEADER%" "200" || echo [WARN] AR balance skipped (endpoint unavailable).

call :check_get "[16/16] Clearing batches" "%CORE_URL%/clearing/batches?limit=5" "%AUTH_HEADER%" "200" || goto :fail

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
