@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_BASE=%GATEWAY_BASE%%AUTH_BASE%/v1/auth"
set "CORE_BASE=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"
set SMOKE_CLIENT_ID=smoke-client
set SMOKE_WEBHOOK_URL=%SMOKE_WEBHOOK_URL%
if "%SMOKE_WEBHOOK_URL%"=="" set SMOKE_WEBHOOK_URL=http://localhost:9999/webhook

set TEMPLATE_BODY={"code":"webhook_test","event_type":"WEBHOOK_TEST","channel":"WEBHOOK","locale":"ru","body":"Webhook payload {event}","content_type":"TEXT","is_active":true,"version":1,"required_vars":["event"]}
set PREF_BODY={"subject_type":"CLIENT","subject_id":"%SMOKE_CLIENT_ID%","event_type":"WEBHOOK_TEST","channel":"WEBHOOK","enabled":true,"address_override":"%SMOKE_WEBHOOK_URL%"}
set OUTBOX_BODY={"event_type":"WEBHOOK_TEST","subject_type":"CLIENT","subject_id":"%SMOKE_CLIENT_ID%","channels":["WEBHOOK"],"template_code":"webhook_test","template_vars":{"event":"ping"},"priority":"NORMAL","dedupe_key":"smoke-webhook-1"}

echo [1/6] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if "%TOKEN%"=="" goto :error

set AUTH_HEADER=Authorization: Bearer %TOKEN%

echo [2/6] Upsert template...
curl -s -o template.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/templates" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d %TEMPLATE_BODY% | findstr /R "200 201" >NUL || goto :error

echo [3/6] Upsert preference...
curl -s -o pref.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/preferences" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d %PREF_BODY% | findstr /R "200 201" >NUL || goto :error

echo [4/6] Enqueue webhook notification...
curl -s -o outbox.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/outbox" -H "Content-Type: application/json" -H "%AUTH_HEADER%" -d %OUTBOX_BODY% | findstr /R "200 201" >NUL || goto :error

echo [5/6] Dispatch notifications...
curl -s -o dispatch.json -w "%%{http_code}" -X POST "%CORE_BASE%/notifications/dispatch" -H "%AUTH_HEADER%" | findstr 200 >NUL || goto :error

echo [6/6] Check delivery logs...
curl -s -o deliveries.json -w "%%{http_code}" "%CORE_BASE%/notifications/deliveries?event_type=WEBHOOK_TEST&channel=WEBHOOK&status=SENT" -H "%AUTH_HEADER%" | findstr 200 >NUL || goto :error

python -c "import json; data=json.load(open('deliveries.json')); print('deliveries', len(data))"

echo OK
exit /b 0

:error
echo Smoke failed. See previous logs.
exit /b 1
