@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%/v1/auth"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=change-me"

set "TOKEN="
set "AUTH_HEADER="
set "INVOICE_ID="
set "TOTAL_WITH_TAX=0"
set "PARTIAL_AMOUNT="
set "REMAINING_AMOUNT="

echo [1/14] Fetch admin token...
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

call :check_get "[2/14] /auth/me" "%AUTH_URL%/me" "%AUTH_HEADER%" "200" || goto :fail
call :check_get "[3/14] Billing periods" "%CORE_URL%/billing/periods?limit=1" "%AUTH_HEADER%" "200" || goto :fail

echo [4/14] Generate draft invoice for transitions...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "{\"period_from\":\"2024-01-01\",\"period_to\":\"2024-01-31\",\"status\":\"DRAFT\"}" -X POST -o generate_invoice.json "%CORE_URL%/billing/invoices/generate"`) do set "CODE=%%c"
if "%CODE%"=="202" (
  for /f "usebackq tokens=*" %%i in (`python -c "import json,sys; data=json.load(open('generate_invoice.json')); ids=data.get('created_ids') or []; print(ids[0] if ids else '')"`) do set "INVOICE_ID=%%i"
) else (
  echo [WARN] Generation returned %CODE%, will reuse existing invoice if present.
)

if "%INVOICE_ID%"=="" (
  echo [5/14] List invoices to obtain id...
  for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoices.json "%CORE_URL%/billing/invoices?limit=1&offset=0"`) do set "CODE=%%c"
  if not "%CODE%"=="200" (
    echo [FAIL] Invoices list returned %CODE%.
    goto :fail
  )
  for /f "usebackq tokens=*" %%i in (`python -c "import json,sys; data=json.load(open('invoices.json')); items=data.get('items') or []; print(items[0]['id'] if items else '')"`) do set "INVOICE_ID=%%i"
)

if "%INVOICE_ID%"=="" (
  echo [FAIL] Could not resolve invoice id.
  goto :fail
)

call :post_step "[6/14] Mark invoice ISSUED" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"ISSUED\",\"reason\":\"smoke\"}" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[7/14] Mark invoice SENT" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"SENT\",\"reason\":\"smoke\"}" "%AUTH_HEADER%" "200" "" || goto :fail

echo [8/14] Fetch invoice totals...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoice_detail.json "%CORE_URL%/billing/invoices/%INVOICE_ID%"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Invoice detail returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%t in (`python -c "import json; d=json.load(open('invoice_detail.json')); print(d.get('total_with_tax') or d.get('total_amount') or 0)"`) do set "TOTAL_WITH_TAX=%%t"
for /f "usebackq tokens=*" %%p in (`python -c "import json; data=json.load(open('invoice_detail.json')); total=int(data.get('total_with_tax') or data.get('total_amount') or 0); partial=max(1,total//2) if total else 0; remaining=max(total-partial,0); print(partial); print(remaining)"`) do (
  if "!PARTIAL_AMOUNT!"=="" (
    set "PARTIAL_AMOUNT=%%p"
  ) else (
    set "REMAINING_AMOUNT=%%p"
  )
)
if "%PARTIAL_AMOUNT%"=="" set "PARTIAL_AMOUNT=1"
if "%REMAINING_AMOUNT%"=="" set "REMAINING_AMOUNT=1"
echo     total=%TOTAL_WITH_TAX%, partial=%PARTIAL_AMOUNT%, remaining=%REMAINING_AMOUNT%

call :post_step "[9/14] Apply partial payment" "%CORE_URL%/finance/payments" "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":%PARTIAL_AMOUNT%,\"currency\":\"RUB\"}" "%AUTH_HEADER%" "201" "200" || goto :fail

call :post_step "[10/14] Apply final payment" "%CORE_URL%/finance/payments" "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":%REMAINING_AMOUNT%,\"currency\":\"RUB\",\"idempotency_key\":\"smoke-final\"}" "%AUTH_HEADER%" "201" "200" || goto :fail

call :post_step "[11/14] Attempt forbidden rollback (PAID->ISSUED)" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"ISSUED\",\"reason\":\"forbidden\"}" "%AUTH_HEADER%" "409" "" || goto :fail

call :post_step "[12/14] Invoice PDF enqueue (best-effort)" "%CORE_URL%/billing/invoices/%INVOICE_ID%/pdf" "" "%AUTH_HEADER%" "200" "202" || echo [WARN] PDF enqueue skipped.

for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -o invoice_final.json "%CORE_URL%/billing/invoices/%INVOICE_ID%"`) do set "CODE=%%c"
if "%CODE%"=="200" (
  echo [13/14] Final invoice state:
  python -c "import json; d=json.load(open('invoice_final.json')); print('status={0}; paid_at={1}; amount_due={2}; amount_paid={3}'.format(d.get('status'), d.get('paid_at'), d.get('amount_due'), d.get('amount_paid')))"
) else (
  echo [WARN] Could not fetch final invoice (%CODE%).
)

call :check_get "[14/14] Clearing batches" "%CORE_URL%/clearing/batches?limit=1" "%AUTH_HEADER%" "200" || echo [WARN] Clearing check skipped.

echo [SMOKE] Invoice state machine smoke completed.
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
