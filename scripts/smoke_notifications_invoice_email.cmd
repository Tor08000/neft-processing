@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"
if "%SMOKE_NOTIFICATION_EMAIL%"=="" (
  set "SMOKE_NOTIFICATION_EMAIL=smoke@example.com"
)
if "%MAILPIT_URL%"=="" set "MAILPIT_URL=http://localhost:8025/api/v1/messages"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "ADMIN_ROOT=%CORE_API_BASE%%CORE_BASE%/v1/admin"
set "TMP_DIR=%~dp0_tmp\smoke_notifications_invoice_email"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1

set "CLIENT_LOGIN_BODY=%TMP_DIR%\client_login_body.json"
set "CLIENT_LOGIN_FILE=%TMP_DIR%\client_login.json"
set "CLIENT_PORTAL_FILE=%TMP_DIR%\client_portal_me.json"
set "TEMPLATE_BODY_FILE=%TMP_DIR%\template_body.json"
set "TEMPLATE_FILE=%TMP_DIR%\template.json"
set "PREF_BODY_FILE=%TMP_DIR%\pref_body.json"
set "PREF_FILE=%TMP_DIR%\pref.json"
set "INVOICE_BODY_FILE=%TMP_DIR%\invoice_body.json"
set "INVOICE_FILE=%TMP_DIR%\invoice.json"
set "DISPATCH_FILE=%TMP_DIR%\dispatch.json"
set "DELIVERIES_FILE=%TMP_DIR%\deliveries.json"
set "MAILPIT_FILE=%TMP_DIR%\mailpit_messages.json"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "ADMIN_AUTH_HEADER="
set "CLIENT_AUTH_HEADER="
set "CLIENT_ID="
set "MAILPIT_CODE="

echo [0/7] Check Mailpit...
for /f "usebackq tokens=*" %%c in (`curl -s -o "%MAILPIT_FILE%" -w "%%{http_code}" "%MAILPIT_URL%"`) do set "MAILPIT_CODE=%%c"
if not "%MAILPIT_CODE%"=="200" (
  echo [SKIP] Mailpit unavailable. Email notifications remain explicit local-infra optional.
  exit /b 0
)

echo [1/7] Resolve seeded client context...
python -c "import json; from pathlib import Path; Path(r'%CLIENT_LOGIN_BODY%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%', 'password': r'%CLIENT_PASSWORD%', 'portal': 'client'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%CLIENT_LOGIN_BODY%" "200" "%CLIENT_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%t"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] client login missing access_token
  goto :fail
)
set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"
call :http_request "GET" "%CORE_ROOT%/portal/me" "%CLIENT_AUTH_HEADER%" "" "200" "%CLIENT_PORTAL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_PORTAL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); org=data.get('org') or {}; print(org.get('id') or '')"`) do set "CLIENT_ID=%%t"
if "%CLIENT_ID%"=="" (
  echo [FAIL] client portal/me did not return org id
  type "%CLIENT_PORTAL_FILE%"
  goto :fail
)

echo [2/7] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "ADMIN_TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%ADMIN_TOKEN%"=="" exit /b 1
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [3/7] Upsert template...
python -c "import json; from pathlib import Path; Path(r'%TEMPLATE_BODY_FILE%').write_text(json.dumps({'code':'invoice_issued_email','event_type':'INVOICE_ISSUED','channel':'EMAIL','locale':'ru','subject':'Invoice {invoice_number}','body':'Hello {client_name}, invoice {invoice_number} amount {amount}','content_type':'TEXT','is_active':True,'version':1,'required_vars':['invoice_number','client_name','amount']}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/notifications/templates" "%ADMIN_AUTH_HEADER%" "%TEMPLATE_BODY_FILE%" "201" "%TEMPLATE_FILE%" "200" || goto :fail

echo [4/7] Upsert preference...
python -c "import json; from pathlib import Path; Path(r'%PREF_BODY_FILE%').write_text(json.dumps({'subject_type':'CLIENT','subject_id':r'%CLIENT_ID%','event_type':'INVOICE_ISSUED','channel':'EMAIL','enabled':True,'address_override':r'%SMOKE_NOTIFICATION_EMAIL%'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/notifications/preferences" "%ADMIN_AUTH_HEADER%" "%PREF_BODY_FILE%" "200" "%PREF_FILE%" "201" || goto :fail

echo [5/7] Issue invoice...
python -c "import json; from pathlib import Path; Path(r'%INVOICE_BODY_FILE%').write_text(json.dumps({'client_id':r'%CLIENT_ID%','currency':'RUB','amount_total':100,'due_at':'2025-01-01T00:00:00Z','idempotency_key':'smoke-invoice-email-1'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/billing/flows/invoices" "%ADMIN_AUTH_HEADER%" "%INVOICE_BODY_FILE%" "201" "%INVOICE_FILE%" "200" || goto :fail

echo [6/7] Dispatch notifications...
call :http_request "POST" "%ADMIN_ROOT%/notifications/dispatch" "%ADMIN_AUTH_HEADER%" "" "200" "%DISPATCH_FILE%" || goto :fail

echo [7/7] Check delivery logs...
call :http_request "GET" "%ADMIN_ROOT%/notifications/deliveries?event_type=INVOICE_ISSUED&channel=EMAIL&status=SENT" "%ADMIN_AUTH_HEADER%" "" "200" "%DELIVERIES_FILE%" || goto :fail
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DELIVERIES_FILE%').read_text(encoding='utf-8', errors='ignore') or '[]'); assert isinstance(data, list); assert data, 'no deliveries'; assert any(str(item.get('status') or '').upper() == 'SENT' and str(item.get('channel') or '').upper() == 'EMAIL' for item in data); print('deliveries', len(data))" || goto :fail
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%MAILPIT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=data.get('messages') or []; assert isinstance(items, list); print('mailpit_messages_before', len(items))" || goto :fail
for /f "usebackq tokens=*" %%c in (`curl -s -o "%MAILPIT_FILE%" -w "%%{http_code}" "%MAILPIT_URL%"`) do set "MAILPIT_CODE=%%c"
if not "%MAILPIT_CODE%"=="200" (
  echo [FAIL] Mailpit recheck returned %MAILPIT_CODE%
  goto :fail
)
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%MAILPIT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=data.get('messages') or []; assert isinstance(items, list); assert items, 'mailpit received no messages'; print('mailpit_messages_after', len(items))" || goto :fail

echo [SMOKE] Notifications invoice email flow completed.
exit /b 0

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "ALT=%~7"
set "CODE="
if "%BODY_FILE%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X "%METHOD%" "%URL%"`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X "%METHOD%" -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X "%METHOD%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%"`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X "%METHOD%" -H "%HEADER%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%"`) do set "CODE=%%c"
  )
)
if "%CODE%"=="%EXPECTED%" exit /b 0
if not "%ALT%"=="" if "%CODE%"=="%ALT%" exit /b 0
echo [FAIL] %METHOD% %URL% expected %EXPECTED% got %CODE%
if exist "%OUT%" type "%OUT%"
exit /b 1

:fail
echo [SMOKE] Failed.
exit /b 1
