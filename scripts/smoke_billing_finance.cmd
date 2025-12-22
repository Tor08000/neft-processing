@echo off
setlocal enabledelayedexpansion

set AUTH_BASE=http://localhost:8002/api/v1/auth
set CORE_BASE=http://localhost:8001/api/v1/admin

echo [1/10] Login to auth-host...
curl -s -S -X POST "%AUTH_BASE%/login" -H "Content-Type: application/json" -d "{\"email\":\"admin@neft.local\",\"password\":\"Admin123!\"}" > token.json || goto :error
python -c "import json, pathlib; pathlib.Path('token.txt').write_text(json.load(open('token.json')).get('access_token',''))" || goto :error
set /p TOKEN=<token.txt
if "%TOKEN%"=="" goto :error

echo [2/10] Check /auth/me...
curl -s -o NUL -w "%%{http_code}" "%AUTH_BASE%/me" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error

echo [3/10] List billing periods...
curl -s -o periods.json -w "%%{http_code}" "%CORE_BASE%/billing/periods" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error

echo [4/10] Run ADHOC billing...
set "BODY={\"period_type\":\"ADHOC\",\"start_at\":\"2024-01-01T00:00:00Z\",\"end_at\":\"2024-01-02T00:00:00Z\",\"tz\":\"UTC\"}"
curl -s -o billing_run.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/run" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d %BODY% | findstr 200 >NUL || goto :error

echo [5/10] List invoices...
curl -s -o invoices.json -w "%%{http_code}" "%CORE_BASE%/billing/invoices?limit=50&offset=0" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error
python -c "import json, pathlib; data=json.load(open('invoices.json')); items=data.get('items') or []; pathlib.Path('invoice_id.txt').write_text(items[0]['id']) if items else None"

if exist invoice_id.txt (
  set /p INVOICE_ID=<invoice_id.txt
  if not "%INVOICE_ID%"=="" (
    echo [6/10] Enqueue PDF for invoice %INVOICE_ID%...
    curl -s -o pdf_task.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/invoices/%INVOICE_ID%/pdf" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error

    echo [7/10] Fetch invoice with PDF link...
    curl -s -o invoice.json -w "%%{http_code}" "%CORE_BASE%/billing/invoices/%INVOICE_ID%" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error
    python -c "import json; inv=json.load(open('invoice.json')); url=inv.get('pdf_url') or inv.get('download_url'); print('PDF URL:', url or 'pending')"
  ) else (
    echo No invoices yet, skipping PDF steps.
  )
) else (
  echo No invoices yet, skipping PDF steps.
)

echo [8/10] Finance payment (best-effort)...
curl -s -o payment.json -w "%%{http_code}" -X POST "%CORE_BASE%/finance/payments" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"client_id\":\"demo-client\",\"amount\":1,\"currency\":\"RUB\",\"occurred_at\":\"2024-01-02T00:00:00Z\",\"external_ref\":\"smoke\"}" | findstr /R "200 201" >NUL

echo [9/10] Fetch AR balance (best-effort)...
curl -s -o balance.json -w "%%{http_code}" "%CORE_BASE%/finance/ar/balance?client_id=demo-client" -H "Authorization: Bearer %TOKEN%" | findstr /R "200 404" >NUL

echo [10/10] Clearing run...
curl -s -o clearing_run.json -w "%%{http_code}" -X POST "%CORE_BASE%/clearing/run?date=2024-01-02" -H "Authorization: Bearer %TOKEN%" | findstr /R "200 202" >NUL
curl -s -o clearing_batches.json -w "%%{http_code}" "%CORE_BASE%/clearing/batches?limit=5" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL

echo OK
exit /b 0

:error
echo Smoke failed. See previous logs.
exit /b 1
