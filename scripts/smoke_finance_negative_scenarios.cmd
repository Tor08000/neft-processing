@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ===== Finance negative scenarios smoke =====

set AUTH_URL=http://localhost:8002/api/v1/auth/login
set CORE_ADMIN=http://localhost/api/v1/admin
set CORE_PUBLIC=http://localhost/api/v1

echo Logging in as admin...
curl -s -X POST "%AUTH_URL%" -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}" > admin_token.json
python -c "import json,sys; data=json.load(open('admin_token.json')); sys.stdout.write(data.get('access_token',''))" > admin_token.txt
set /p ADMIN_TOKEN=<admin_token.txt
if "%ADMIN_TOKEN%"=="" (
  echo [ERROR] Failed to acquire admin token.
  goto :eof
)

echo Seeding demo billing data...
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -X POST "%CORE_ADMIN%/billing/seed" > seed.json

echo Fetching demo client invoices...
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" "%CORE_ADMIN%/billing/invoices?client_id=demo-client" > invoices.json
for /f %%A in ('powershell -NoLogo -Command "(Get-Content invoices.json | ConvertFrom-Json).items[0].id"') do set INVOICE_ID=%%A

if "%INVOICE_ID%"=="" (
  echo [ERROR] No invoice found for demo-client.
  goto :eof
)

echo Using invoice !INVOICE_ID!

echo ===== SCN-1 Partial payment (admin finance endpoint) =====
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" -X POST "%CORE_ADMIN%/finance/payments" ^
  -d "{\"invoice_id\":\"!INVOICE_ID!\",\"amount\":4000,\"currency\":\"RUB\",\"idempotency_key\":\"scn1-pay-1\"}" > scn1_partial.json
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" -X POST "%CORE_ADMIN%/finance/payments" ^
  -d "{\"invoice_id\":\"!INVOICE_ID!\",\"amount\":4000,\"currency\":\"RUB\",\"idempotency_key\":\"scn1-pay-1\"}" > scn1_partial_replay.json
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" -X POST "%CORE_ADMIN%/finance/payments" ^
  -d "{\"invoice_id\":\"!INVOICE_ID!\",\"amount\":6000,\"currency\":\"RUB\",\"idempotency_key\":\"scn1-pay-2\"}" > scn1_full.json

echo ===== SCN-2/SCN-3/SCN-4 =====
echo NOTE: Use a fresh invoice (reset the DB or seed another billing period) before running the next scenarios.

endlocal
