@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "ADMIN_ROOT=%CORE_API_BASE%%CORE_BASE%/v1/admin"
set "TMP_DIR=%~dp0_tmp\smoke_notifications_webhook"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1

set "CLIENT_LOGIN_BODY=%TMP_DIR%\client_login_body.json"
set "CLIENT_LOGIN_FILE=%TMP_DIR%\client_login.json"
set "CLIENT_PORTAL_FILE=%TMP_DIR%\client_portal_me.json"
set "TEMPLATE_BODY_FILE=%TMP_DIR%\template_body.json"
set "TEMPLATE_FILE=%TMP_DIR%\template.json"
set "PREF_BODY_FILE=%TMP_DIR%\pref_body.json"
set "PREF_FILE=%TMP_DIR%\pref.json"
set "OUTBOX_BODY_FILE=%TMP_DIR%\outbox_body.json"
set "OUTBOX_FILE=%TMP_DIR%\outbox.json"
set "DISPATCH_FILE=%TMP_DIR%\dispatch.json"
set "DELIVERIES_FILE=%TMP_DIR%\deliveries.json"
set "WEBHOOK_SINK_PY=%TMP_DIR%\webhook_sink.py"
set "WEBHOOK_CAPTURE_FILE=%TMP_DIR%\webhook_capture.json"
set "WEBHOOK_LOG_FILE=%TMP_DIR%\webhook_sink.log"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "ADMIN_AUTH_HEADER="
set "CLIENT_AUTH_VALUE="
set "CLIENT_AUTH_HEADER="
set "CLIENT_ID="
set "WEBHOOK_PORT=18999"
set "LOCAL_SINK_STARTED=0"
set "SMOKE_RUN_ID=%RANDOM%%RANDOM%"
set "SMOKE_TEMPLATE_CODE=webhook_test_%SMOKE_RUN_ID%"
set "SMOKE_DEDUPE_KEY=smoke-webhook-%SMOKE_RUN_ID%"
set "SMOKE_WEBHOOK_URL=%SMOKE_WEBHOOK_URL%"
if "%SMOKE_WEBHOOK_URL%"=="" set "SMOKE_WEBHOOK_URL=http://host.docker.internal:%WEBHOOK_PORT%/webhook"

echo [1/7] Resolve seeded client context...
python -c "import json; from pathlib import Path; Path(r'%CLIENT_LOGIN_BODY%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%', 'password': r'%CLIENT_PASSWORD%', 'portal': 'client'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%CLIENT_LOGIN_BODY%" "200" "%CLIENT_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%t"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] client login missing access_token
  goto :fail
)
set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
set "CLIENT_AUTH_VALUE=Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_VALUE=%CLIENT_TOKEN%"
python -c "from pathlib import Path; import sys, urllib.request; req = urllib.request.Request(r'%CORE_ROOT%/portal/me', headers={'Authorization': r'%CLIENT_AUTH_VALUE%'}); resp = urllib.request.urlopen(req, timeout=20); body = resp.read(); Path(r'%CLIENT_PORTAL_FILE%').write_bytes(body); sys.exit(0 if getattr(resp, 'status', 200) == 200 else 1)" || goto :fail
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

if not exist "%WEBHOOK_CAPTURE_FILE%" (
  echo [3/7] Start local webhook sink...
  python -c "from pathlib import Path; Path(r'%WEBHOOK_SINK_PY%').write_text('''from http.server import BaseHTTPRequestHandler, HTTPServer\nfrom pathlib import Path\nimport sys\n\ncapture = Path(sys.argv[1])\nport = int(sys.argv[2])\n\n\nclass Handler(BaseHTTPRequestHandler):\n    def do_POST(self):\n        length = int(self.headers.get(\"Content-Length\", \"0\"))\n        body = self.rfile.read(length)\n        capture.write_text(body.decode(\"utf-8\", errors=\"ignore\"), encoding=\"utf-8\")\n        self.send_response(200)\n        self.end_headers()\n        self.wfile.write(b\"ok\")\n\n    def log_message(self, format, *args):\n        return\n\n\nserver = HTTPServer((\"0.0.0.0\", port), Handler)\nserver.timeout = 15\nserver.handle_request()\nserver.server_close()\n''', encoding='ascii')" || goto :fail
  del /q "%WEBHOOK_CAPTURE_FILE%" 2>nul
  start "" /B python "%WEBHOOK_SINK_PY%" "%WEBHOOK_CAPTURE_FILE%" "%WEBHOOK_PORT%" > "%WEBHOOK_LOG_FILE%" 2>&1
  powershell -NoProfile -Command "Start-Sleep -Seconds 1" >nul
  set "LOCAL_SINK_STARTED=1"
)

echo [4/7] Upsert template and preference...
python -c "import json; from pathlib import Path; Path(r'%TEMPLATE_BODY_FILE%').write_text(json.dumps({'code':r'%SMOKE_TEMPLATE_CODE%','event_type':'WEBHOOK_TEST','channel':'WEBHOOK','locale':'ru','body':'Webhook payload {event}','content_type':'TEXT','is_active':True,'version':1,'required_vars':['event']}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/notifications/templates" "%ADMIN_AUTH_HEADER%" "%TEMPLATE_BODY_FILE%" "201" "%TEMPLATE_FILE%" "200" || goto :fail
python -c "import json; from pathlib import Path; Path(r'%PREF_BODY_FILE%').write_text(json.dumps({'subject_type':'CLIENT','subject_id':r'%CLIENT_ID%','event_type':'WEBHOOK_TEST','channel':'WEBHOOK','enabled':True,'address_override':r'%SMOKE_WEBHOOK_URL%'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/notifications/preferences" "%ADMIN_AUTH_HEADER%" "%PREF_BODY_FILE%" "200" "%PREF_FILE%" "201" || goto :fail

echo [5/7] Enqueue webhook notification...
python -c "import json; from pathlib import Path; Path(r'%OUTBOX_BODY_FILE%').write_text(json.dumps({'event_type':'WEBHOOK_TEST','subject_type':'CLIENT','subject_id':r'%CLIENT_ID%','channels':['WEBHOOK'],'template_code':r'%SMOKE_TEMPLATE_CODE%','template_vars':{'event':'ping'}, 'priority':'NORMAL','dedupe_key':r'%SMOKE_DEDUPE_KEY%'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/notifications/outbox" "%ADMIN_AUTH_HEADER%" "%OUTBOX_BODY_FILE%" "200" "%OUTBOX_FILE%" "201" || goto :fail

echo [6/7] Dispatch notifications...
call :http_request "POST" "%ADMIN_ROOT%/notifications/dispatch" "%ADMIN_AUTH_HEADER%" "" "200" "%DISPATCH_FILE%" || goto :fail

echo [7/7] Check delivery logs...
call :http_request "GET" "%ADMIN_ROOT%/notifications/deliveries?event_type=WEBHOOK_TEST&channel=WEBHOOK&status=SENT" "%ADMIN_AUTH_HEADER%" "" "200" "%DELIVERIES_FILE%" || goto :fail
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DELIVERIES_FILE%').read_text(encoding='utf-8', errors='ignore') or '[]'); assert isinstance(data, list); assert data, 'no webhook deliveries'; assert any(str(item.get('status') or '').upper() == 'SENT' and str(item.get('channel') or '').upper() == 'WEBHOOK' for item in data); print('deliveries', len(data))" || goto :fail
if "%LOCAL_SINK_STARTED%"=="1" (
  call :wait_for_file "%WEBHOOK_CAPTURE_FILE%" 10 1 || goto :fail
  python -c "import json; from pathlib import Path; data=json.loads(Path(r'%WEBHOOK_CAPTURE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); assert data.get('event_type') == 'WEBHOOK_TEST'; print('webhook_payload_ok', data.get('event_type'))" || goto :fail
)

echo [SMOKE] Notifications webhook flow completed.
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

:wait_for_file
set "WAIT_FILE=%~1"
set "WAIT_ATTEMPTS=%~2"
set "WAIT_DELAY=%~3"
if "%WAIT_ATTEMPTS%"=="" set "WAIT_ATTEMPTS=10"
if "%WAIT_DELAY%"=="" set "WAIT_DELAY=1"
for /l %%i in (1,1,%WAIT_ATTEMPTS%) do (
  if exist "%WAIT_FILE%" exit /b 0
  if not "%%i"=="%WAIT_ATTEMPTS%" powershell -NoProfile -Command "Start-Sleep -Seconds %WAIT_DELAY%" >nul
)
echo [FAIL] webhook capture file did not appear: %WAIT_FILE%
if exist "%WEBHOOK_LOG_FILE%" type "%WEBHOOK_LOG_FILE%"
exit /b 1

:fail
echo [SMOKE] Failed.
if exist "%WEBHOOK_LOG_FILE%" type "%WEBHOOK_LOG_FILE%"
exit /b 1
