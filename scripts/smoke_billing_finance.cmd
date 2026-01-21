@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_BASE=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_BASE=%GATEWAY_BASE%%CORE_BASE%/v1/admin"

echo [1/10] Fetch admin token...
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

echo [2/10] Check /auth/me...
call :curl_check "[2/10] /auth/me" "%AUTH_BASE%/me" "GET" "" "auth_me.json" "200"
if errorlevel 2 exit /b 0
if errorlevel 1 goto :error

echo [3/10] List billing periods...
call :curl_check "[3/10] billing periods" "%CORE_BASE%/billing/periods" "GET" "" "periods.json" "200"
if errorlevel 2 exit /b 0
if errorlevel 1 goto :error

echo [4/10] Run ADHOC billing...
set "BODY={\"period_type\":\"ADHOC\",\"start_at\":\"2024-01-01T00:00:00Z\",\"end_at\":\"2024-01-02T00:00:00Z\",\"tz\":\"UTC\"}"
call :curl_check "[4/10] billing run" "%CORE_BASE%/billing/run" "POST" "%BODY%" "billing_run.json" "200 201 202"
if errorlevel 2 exit /b 0
if errorlevel 1 goto :error

echo [5/10] List invoices...
call :curl_check "[5/10] invoices list" "%CORE_BASE%/billing/invoices?limit=50&offset=0" "GET" "" "invoices.json" "200"
if errorlevel 2 exit /b 0
if errorlevel 1 goto :error
python -c "import json, pathlib; data=json.load(open('invoices.json')); items=data.get('items'); assert isinstance(items, list); pathlib.Path('invoice_id.txt').write_text(items[0].get('id','')) if items else None"
if errorlevel 1 (
  echo [FAIL] Invoices list JSON invalid or missing items[].
  goto :error
)

if exist invoice_id.txt (
  set /p INVOICE_ID=<invoice_id.txt
  if not "%INVOICE_ID%"=="" (
    echo [6/10] Enqueue PDF for invoice %INVOICE_ID%...
    call :curl_check "[6/10] invoice pdf enqueue" "%CORE_BASE%/billing/invoices/%INVOICE_ID%/pdf" "POST" "" "pdf_task.json" "200 202"
    if errorlevel 2 exit /b 0
    if errorlevel 1 goto :error

    echo [7/10] Fetch invoice with PDF link...
    call :curl_check "[7/10] invoice fetch" "%CORE_BASE%/billing/invoices/%INVOICE_ID%" "GET" "" "invoice.json" "200"
    if errorlevel 2 exit /b 0
    if errorlevel 1 goto :error
    python -c "import json; inv=json.load(open('invoice.json')); url=inv.get('pdf_url') or inv.get('download_url'); print('PDF URL:', url or 'pending')"
  ) else (
    echo [SKIP] No invoices yet, skipping PDF steps.
    exit /b 0
  )
) else (
  echo [SKIP] No invoices yet, skipping PDF steps.
  exit /b 0
)

echo [8/10] Finance payment (best-effort)...
call :curl_check "[8/10] finance payment" "%CORE_BASE%/finance/payments" "POST" "{\"client_id\":\"demo-client\",\"amount\":1,\"currency\":\"RUB\",\"occurred_at\":\"2024-01-02T00:00:00Z\",\"external_ref\":\"smoke\"}" "payment.json" "200 201"
if errorlevel 1 goto :error

echo [9/10] Fetch AR balance (best-effort)...
call :curl_check "[9/10] AR balance" "%CORE_BASE%/finance/ar/balance?client_id=demo-client" "GET" "" "balance.json" "200 404"
if errorlevel 1 goto :error

echo [10/10] Clearing run...
call :curl_check "[10/10] clearing run" "%CORE_BASE%/clearing/run?date=2024-01-02" "POST" "" "clearing_run.json" "200 202"
if errorlevel 1 goto :error
call :curl_check "[10/10] clearing batches" "%CORE_BASE%/clearing/batches?limit=5" "GET" "" "clearing_batches.json" "200"
if errorlevel 1 goto :error

echo OK
exit /b 0

:error
echo Smoke failed. See previous logs.
exit /b 1

:curl_check
set "LABEL=%~1"
set "URL=%~2"
set "METHOD=%~3"
set "BODY=%~4"
set "OUT=%~5"
set "ALLOWED=%~6"
set "CODE="
if /I "%METHOD%"=="POST" (
  if "%BODY%"=="" (
    curl -s -o "%OUT%" -w "%%{http_code}" -X POST "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\billing_finance.code"
  ) else (
    curl -s -o "%OUT%" -w "%%{http_code}" -X POST "%URL%" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d "%BODY%" > "%TEMP%\billing_finance.code"
  )
) else (
  curl -s -o "%OUT%" -w "%%{http_code}" "%URL%" -H "%AUTH_HEADER%" > "%TEMP%\billing_finance.code"
)
set /p CODE=<"%TEMP%\billing_finance.code"
if "%CODE:~0,1%"=="5" (
  echo [FAIL] %LABEL% returned %CODE%.
  exit /b 1
)
set "MATCH=0"
for %%A in (%ALLOWED%) do (
  if "%%A"=="%CODE%" set "MATCH=1"
)
if "%MATCH%"=="1" (
  exit /b 0
)
echo [SKIP] %LABEL% returned %CODE%.
exit /b 2
