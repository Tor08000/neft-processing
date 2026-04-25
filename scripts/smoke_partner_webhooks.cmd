@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" (
  if "%INTEGRATION_HUB_BASE%"=="" set "INTEGRATION_HUB_BASE=http://localhost:8010"
  if "%INT_BASE%"=="" set "INT_BASE="
) else (
  if "%INTEGRATION_HUB_BASE%"=="" set "INTEGRATION_HUB_BASE=%GATEWAY_BASE%"
  if "%INT_BASE%"=="" set "INT_BASE=/api/int"
)
set "BASE_URL=%INTEGRATION_HUB_BASE%%INT_BASE%"
set "OWNER_ID=partner-smoke"
set "ENDPOINT_ID="
set "SUBSCRIPTION_ID="
set "CREATE_BODY=%TEMP%\\neft_webhook_create.json"
set "SUBSCRIPTION_BODY=%TEMP%\\neft_webhook_subscription.json"
set "TEST_BODY=%TEMP%\\neft_webhook_test.json"
set "REPLAY_BODY=%TEMP%\\neft_webhook_replay.json"

echo [1/7] Integration-hub health...
call :check_get "[1/7] /health" "%BASE_URL%/health" "200" || goto :fail

echo [2/7] Create partner webhook endpoint...
python -c "import json, pathlib; pathlib.Path(r'%CREATE_BODY%').write_text(json.dumps({'owner_type':'PARTNER','owner_id':'%OWNER_ID%','url':'https://example.com/webhooks/neft-smoke'}), encoding='utf-8')"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%CREATE_BODY%" -o webhook_create.json "%BASE_URL%/v1/webhooks/endpoints"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Endpoint create returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; data=json.load(open('webhook_create.json', encoding='utf-8')); print(data.get('id',''))"`) do set "ENDPOINT_ID=%%i"
if "%ENDPOINT_ID%"=="" (
  echo [FAIL] Endpoint id was not returned.
  goto :fail
)
echo [OK] Endpoint created: %ENDPOINT_ID%

echo [3/7] List partner webhook endpoints...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -o webhook_list.json "%BASE_URL%/v1/webhooks/endpoints?owner_type=PARTNER&owner_id=%OWNER_ID%"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Endpoint list returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; items=json.load(open('webhook_list.json', encoding='utf-8')); print(sum(1 for item in items if item.get('id')=='%ENDPOINT_ID%'))"`) do set "MATCHED=%%i"
if not "%MATCHED%"=="1" (
  echo [FAIL] Created endpoint not found in list.
  goto :fail
)
echo [OK] Endpoint listed.

echo [4/7] Rotate endpoint secret...
call :post_no_body "[4/7] rotate-secret" "%BASE_URL%/v1/webhooks/endpoints/%ENDPOINT_ID%/rotate-secret" "200" || goto :fail

echo [5/7] Create webhook subscription...
python -c "import json, pathlib; pathlib.Path(r'%SUBSCRIPTION_BODY%').write_text(json.dumps({'endpoint_id':'%ENDPOINT_ID%','event_type':'docs.ready','schema_version':1,'enabled':True}), encoding='utf-8')"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%SUBSCRIPTION_BODY%" -o webhook_subscription.json "%BASE_URL%/v1/webhooks/subscriptions"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Subscription create returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; data=json.load(open('webhook_subscription.json', encoding='utf-8')); print(data.get('id',''))"`) do set "SUBSCRIPTION_ID=%%i"
if "%SUBSCRIPTION_ID%"=="" (
  echo [FAIL] Subscription id was not returned.
  goto :fail
)
echo [OK] Subscription created: %SUBSCRIPTION_ID%

echo [6/7] Enqueue webhook test delivery...
python -c "import json, pathlib; pathlib.Path(r'%TEST_BODY%').write_text(json.dumps({'event_type':'docs.ready','payload':{'doc_id':'smoke-doc-1'}}), encoding='utf-8')"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%TEST_BODY%" -o webhook_test.json "%BASE_URL%/v1/webhooks/endpoints/%ENDPOINT_ID%/test"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Test delivery returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%s in (`python -c "import json; data=json.load(open('webhook_test.json', encoding='utf-8')); print(data.get('status',''))"`) do set "DELIVERY_STATUS=%%s"
if /I not "%DELIVERY_STATUS%"=="PENDING" (
  echo [FAIL] Unexpected delivery status %DELIVERY_STATUS%.
  goto :fail
)
echo [OK] Test delivery enqueued.

echo [7/7] Replay stored deliveries...
python -c "import json, pathlib; pathlib.Path(r'%REPLAY_BODY%').write_text(json.dumps({'from':'2000-01-01T00:00:00Z','to':'2100-01-01T00:00:00Z','event_types':['docs.ready'],'only_failed':False}), encoding='utf-8')"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "Content-Type: application/json" --data-binary "@%REPLAY_BODY%" -o webhook_replay.json "%BASE_URL%/v1/webhooks/endpoints/%ENDPOINT_ID%/replay"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Replay returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; data=json.load(open('webhook_replay.json', encoding='utf-8')); print(data.get('scheduled_deliveries',0))"`) do set "REPLAY_COUNT=%%i"
if "%REPLAY_COUNT%"=="0" (
  echo [FAIL] Replay did not schedule any deliveries.
  goto :fail
)
echo [OK] Replay scheduled %REPLAY_COUNT% deliveries.

echo [SMOKE] Partner webhooks self-service completed.
call :cleanup
exit /b 0

:check_get
set "LABEL=%~1"
set "URL=%~2"
set "EXPECTED=%~3"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:post_no_body
set "LABEL=%~1"
set "URL=%~2"
set "EXPECTED=%~3"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -X POST "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:fail
call :cleanup
echo [SMOKE] Failed.
exit /b 1

:cleanup
del /q "%CREATE_BODY%" 2>nul
del /q "%SUBSCRIPTION_BODY%" 2>nul
del /q "%TEST_BODY%" 2>nul
del /q "%REPLAY_BODY%" 2>nul
exit /b 0
