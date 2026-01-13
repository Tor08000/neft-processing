@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ===== Billing smoke =====

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "CORE_BILLING=%GATEWAY_BASE%%CORE_BASE%/v1/admin/billing"

set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1

echo Token acquired.

echo Listing billing periods...
curl -s -H "Authorization: Bearer %TOKEN%" "%CORE_BILLING%/periods" > periods.json
type periods.json

echo Starting manual billing run (ADHOC)...
curl -s -H "Authorization: Bearer %TOKEN%" -H "Content-Type: application/json" -d "{\"period_type\":\"ADHOC\",\"start_at\":\"2024-01-01T00:00:00Z\",\"end_at\":\"2024-01-01T23:59:59Z\",\"tz\":\"UTC\",\"client_id\":null}" -X POST "%CORE_BILLING%/run" > billing_run.json
type billing_run.json

echo Fetching invoices...
curl -s -H "Authorization: Bearer %TOKEN%" "%CORE_BILLING%/invoices" > invoices.json
type invoices.json

if exist invoice_id.txt del invoice_id.txt
python -c "import json, pathlib; data=json.load(open('invoices.json')); items=data.get('items') or []; pathlib.Path('invoice_id.txt').write_text(items[0]['id']) if items else None"
if exist invoice_id.txt set /p INVOICE_ID=<invoice_id.txt

if "%INVOICE_ID%"=="" (
  echo [WARN] No invoices found to generate PDF for.
  goto :eof
)

echo Enqueue PDF generation for !INVOICE_ID! ...
curl -s -H "Authorization: Bearer %TOKEN%" -X POST "%CORE_BILLING%/invoices/!INVOICE_ID!/pdf" > pdf_enqueue.json
type pdf_enqueue.json

echo Checking PDF status...
curl -s -H "Authorization: Bearer %TOKEN%" "%CORE_BILLING%/invoices/!INVOICE_ID!/pdf" > pdf_status.json
type pdf_status.json

echo ===== Done =====
endlocal
