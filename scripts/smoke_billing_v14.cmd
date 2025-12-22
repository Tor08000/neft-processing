@echo off
setlocal enabledelayedexpansion

set AUTH_BASE=http://localhost:8002/api/v1/auth
set CORE_BASE=http://localhost:8001/api/v1/admin

echo [1/9] Login to auth-host...
curl -s -S -X POST "%AUTH_BASE%/login" -H "Content-Type: application/json" -d "{\"email\":\"admin@neft.local\",\"password\":\"Admin123!\"}" > token.json || goto :error
python -c "import json, pathlib; pathlib.Path('token.txt').write_text(json.load(open('token.json')).get('access_token',''))" || goto :error
set /p TOKEN=<token.txt
if "%TOKEN%"=="" goto :error

echo [2/9] Seed demo billing data...
curl -s -o seed.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/seed" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error
python - <<PY
import json, pathlib
seed=json.load(open("seed.json"))
pathlib.Path("period_from.txt").write_text(seed.get("period_from",""))
pathlib.Path("billing_period_id.txt").write_text(seed.get("billing_period_id",""))
pathlib.Path("client_id.txt").write_text(seed.get("client_id",""))
PY

set /p PERIOD_FROM=<period_from.txt
set /p BILLING_PERIOD_ID=<billing_period_id.txt
set /p CLIENT_ID=<client_id.txt
if "%PERIOD_FROM%"=="" goto :error

echo [3/9] Run ADHOC billing...
set "BODY={\"period_type\":\"ADHOC\",\"start_at\":\"%PERIOD_FROM%T00:00:00Z\",\"end_at\":\"%PERIOD_FROM%T23:59:59Z\",\"tz\":\"UTC\",\"client_id\":\"%CLIENT_ID%\",\"idempotency_key\":\"smoke-%PERIOD_FROM%\"}"
curl -s -o billing_run.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/run" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d %BODY% | findstr /R "200 202" >NUL || goto :error

echo [4/9] Clearing run...
curl -s -o clearing_run.json -w "%%{http_code}" -X POST "%CORE_BASE%/clearing/run?clearing_date=%PERIOD_FROM%&idempotency_key=smoke-%PERIOD_FROM%" -H "Authorization: Bearer %TOKEN%" | findstr /R "200 202" >NUL || goto :error

echo [5/9] Fetch invoice...
curl -s -o invoices.json -w "%%{http_code}" "%CORE_BASE%/billing/invoices?period_from=%PERIOD_FROM%&period_to=%PERIOD_FROM%&client_id=%CLIENT_ID%" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error
python - <<PY
import json, pathlib
data=json.load(open("invoices.json"))
items=data.get("items") or []
invoice_id=items[0]["id"] if items else ""
pathlib.Path("invoice_id.txt").write_text(invoice_id)
PY
set /p INVOICE_ID=<invoice_id.txt
if "%INVOICE_ID%"=="" goto :error
echo invoice_id=%INVOICE_ID%

echo [6/9] Generate invoice PDF...
curl -s -o pdf_task.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/invoices/%INVOICE_ID%/pdf?idempotency_key=smoke-%INVOICE_ID%" -H "Authorization: Bearer %TOKEN%" | findstr /R "200 202" >NUL || goto :error
python -c "import json; print('pdf_status', json.load(open('pdf_task.json')).get('pdf_status'))"

echo [7/9] Apply payment...
curl -s -o invoice.json -w "%%{http_code}" "%CORE_BASE%/billing/invoices/%INVOICE_ID%" -H "Authorization: Bearer %TOKEN%" | findstr 200 >NUL || goto :error
python - <<PY
import json, math, pathlib
inv=json.load(open("invoice.json"))
total=int(inv.get("total_with_tax") or inv.get("total_amount") or 0)
amt=max(total//2,1)
pathlib.Path("payment_body.txt").write_text(str(amt))
print("due_before", inv.get("amount_due"))
PY
set /p PAY_AMT=<payment_body.txt
curl -s -o payment.json -w "%%{http_code}" -X POST "%CORE_BASE%/finance/payments" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":%PAY_AMT%,\"currency\":\"RUB\"}" | findstr /R "200 201" >NUL || goto :error

echo [8/9] Credit note...
set /a CREDIT_AMT=%PAY_AMT%/2
if %CREDIT_AMT% LSS 1 set CREDIT_AMT=1
curl -s -o credit.json -w "%%{http_code}" -X POST "%CORE_BASE%/finance/credit-notes" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":%CREDIT_AMT%,\"currency\":\"RUB\",\"reason\":\"smoke\"}" | findstr /R "200 201" >NUL || goto :error

echo [9/9] Reconciliation...
curl -s -o reconcile.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/reconcile" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"billing_period_id\":\"%BILLING_PERIOD_ID%\"}" | findstr /R "200 202" >NUL || goto :error
python -c "import json; print('billing_period_id', json.load(open('reconcile.json')).get('run_id','n/a'))"

echo billing_period_id: %BILLING_PERIOD_ID%
if exist invoice_id.txt (echo invoice_id: %INVOICE_ID%)
if exist pdf_task.json (python -c "import json; print('pdf_status:', json.load(open('pdf_task.json')).get('pdf_status'))")
if exist payment.json (python -c "import json; print('due_after_payment', json.load(open('payment.json')).get('due_amount'))")
if exist credit.json (python -c "import json; print('due_after_credit', json.load(open('credit.json')).get('due_amount'))")

echo OK
exit /b 0

:error
echo Smoke failed. See previous logs.
exit /b 1
