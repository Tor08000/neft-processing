@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ===== Billing smoke =====

set AUTH_URL=http://localhost:8002/api/v1/auth/login
set CORE_BILLING=http://localhost/api/v1/admin/billing

echo Logging in to auth-host...
curl -s -X POST "%AUTH_URL%" -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"Admin123!\"}" > token.json

echo Extracting access token...
python -c "import json; import sys; data=json.load(open('token.json')); sys.stdout.write(data.get('access_token',''))" > token.txt

set /p TOKEN=<token.txt
if "%TOKEN%"=="" (
  echo [ERROR] Failed to extract access token. Check credentials and auth-host.
  goto :eof
)

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

for /f %%A in ('powershell -NoLogo -Command "(Get-Content invoices.json | ConvertFrom-Json).items[0].id"') do set INVOICE_ID=%%A

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
