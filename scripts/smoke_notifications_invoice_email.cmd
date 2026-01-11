@echo off
setlocal enabledelayedexpansion

set AUTH_BASE=http://localhost:8002/api/v1/auth
set CORE_BASE=http://localhost:8001/api/v1/admin
set SMOKE_CLIENT_ID=smoke-client
set SMOKE_EMAIL=%SMOKE_NOTIFICATION_EMAIL%
if "%SMOKE_EMAIL%"=="" set SMOKE_EMAIL=smoke@example.com

set TEMPLATE_BODY={"code":"invoice_issued_email","event_type":"INVOICE_ISSUED","channel":"EMAIL","locale":"ru","subject":"Invoice {invoice_number}","body":"Hello {client_name}, invoice {invoice_number} amount {amount}","content_type":"TEXT","is_active":true,"version":1,"required_vars":["invoice_number","client_name","amount"]}
set PREF_BODY={"subject_type":"CLIENT","subject_id":"%SMOKE_CLIENT_ID%","event_type":"INVOICE_ISSUED","channel":"EMAIL","enabled":true,"address_override":"%SMOKE_EMAIL%"}
set INVOICE_BODY={"client_id":"%SMOKE_CLIENT_ID%","currency":"RUB","amount_total":100,"due_at":"2025-01-01T00:00:00Z","idempotency_key":"smoke-invoice-email-1"}

echo [1/6] Login to auth-host...
curl -s -S -X POST "%AUTH_BASE%/login" -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}" > token.json || goto :error
python -c "import json, pathlib; pathlib.Path('token.txt').write_text(json.load(open('token.json')).get('access_token',''))" || goto :error
set /p TOKEN=<token.txt
if "%TOKEN%"=="" goto :error

set AUTH_HEADER=Authorization: Bearer %TOKEN%

echo [2/6] Upsert template...
curl -s -o template.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/templates" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d %TEMPLATE_BODY% | findstr /R "200 201" >NUL || goto :error

echo [3/6] Upsert preference...
curl -s -o pref.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/preferences" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d %PREF_BODY% | findstr /R "200 201" >NUL || goto :error

echo [4/6] Issue invoice...
curl -s -o invoice.json -w "%%{http_code}" -X POST "%CORE_BASE%/billing/flows/invoices" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d %INVOICE_BODY% | findstr /R "200 201" >NUL || goto :error

echo [5/6] Dispatch notifications...
curl -s -o dispatch.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/dispatch" -H "%AUTH_HEADER%" | findstr 200 >NUL || goto :error

echo [6/6] Check delivery logs...
curl -s -o deliveries.json -w "%%{http_code}" "%CORE_BASE%/notifications/deliveries?event_type=INVOICE_ISSUED&channel=EMAIL&status=SENT" -H "%AUTH_HEADER%" | findstr 200 >NUL || goto :error

python -c "import json; data=json.load(open('deliveries.json')); print('deliveries', len(data))"

echo OK
exit /b 0

:error
echo Smoke failed. See previous logs.
exit /b 1
