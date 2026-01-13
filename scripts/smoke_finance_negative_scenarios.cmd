@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ===== Finance negative scenarios smoke =====

set CORE_ADMIN=http://localhost/api/v1/admin
set CORE_PUBLIC=http://localhost/api/v1

echo Fetching admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "ADMIN_TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%ADMIN_TOKEN%"=="" exit /b 1

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
