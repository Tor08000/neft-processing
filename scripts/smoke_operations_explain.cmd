@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"

set "CLIENT_LOGIN_FILE=%TEMP%\ops_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\ops_client_login_body_%RANDOM%.json"
set "CLIENT_VERIFY_FILE=%TEMP%\ops_client_verify_%RANDOM%.txt"
set "PORTAL_ME_FILE=%TEMP%\ops_portal_me_%RANDOM%.json"
set "LIST_FILE=%TEMP%\ops_list_%RANDOM%.json"
set "DETAIL_FILE=%TEMP%\ops_detail_%RANDOM%.json"
set "EXPLAIN_FILE=%TEMP%\ops_explain_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\ops_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\ops_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\ops_seed_%RANDOM%.log"

set "CLIENT_TOKEN="
set "CLIENT_ID="
set "CLIENT_AUTH_HEADER="

set "OPERATION_UUID=6d43020d-1cf9-4b6f-bd8f-589d4cb3f781"
set "OPERATION_ID=SMOKE-OPS-DECLINE-001"

echo [0/7] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/7] Check auth + core surfaces...
set "AUTH_CODE="
call :resolve_auth_openapi || goto :fail
if "%AUTH_CODE%"=="" (
  echo [FAIL] auth host is not reachable at %AUTH_URL%
  goto :fail
)
if not "%AUTH_CODE%"=="200" (
  echo [FAIL] auth host expected 200 from a mounted OpenAPI route near %AUTH_URL%, got %AUTH_CODE%
  goto :fail
)
call :wait_for_status "%CORE_API_BASE%/health" "200" 20 2 || goto :fail
call :http_request "GET" "%CORE_API_BASE%/health" "" "" "200" "%CORE_HEALTH_FILE%" || goto :fail

echo [1/7] Login client...
python -c "import json; from pathlib import Path; Path(r'%CLIENT_LOGIN_BODY%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%','password': r'%CLIENT_PASSWORD%','portal':'client'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%CLIENT_LOGIN_BODY%" "200" "%CLIENT_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('client_id',''))"`) do set "CLIENT_ID=%%t"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] client login missing access_token
  goto :fail
)
if "%CLIENT_ID%"=="" (
  echo [FAIL] client login missing client_id
  goto :fail
)
set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

echo [2/7] Verify client auth and portal context...
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%CLIENT_AUTH_HEADER%" "" "204" "%CLIENT_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/portal/me" "%CLIENT_AUTH_HEADER%" "" "200" "%PORTAL_ME_FILE%" || goto :fail

echo [3/7] Seed one declined operation for client detail flow...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo INSERT INTO operations ^(id, operation_id, created_at, updated_at, operation_type, status, merchant_id, terminal_id, client_id, card_id, amount, amount_settled, currency, captured_amount, refunded_amount, authorized, response_code, response_message, reason, risk_result, risk_score^) VALUES ^('%OPERATION_UUID%', '%OPERATION_ID%', timezone^('utc', now^(^)^), timezone^('utc', now^(^)^), 'DECLINE', 'DECLINED', 'SMOKE_MERCHANT', 'SMOKE_TERMINAL', '%CLIENT_ID%', 'SMOKE-CARD-001', 1500, 0, 'RUB', 0, 0, false, '05', 'DECLINED', 'RISK_DECLINE', 'BLOCK', 0.97^) ON CONFLICT ^(operation_id^) DO UPDATE SET client_id = EXCLUDED.client_id, updated_at = EXCLUDED.updated_at, status = EXCLUDED.status, reason = EXCLUDED.reason, risk_result = EXCLUDED.risk_result, risk_score = EXCLUDED.risk_score;
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] operations seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/7] Load operations list...
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/operations?limit=10" "%CLIENT_AUTH_HEADER%" "" "200" "%LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ids={str(item.get('id')) for item in payload.get('items') or []}; print('%OPERATION_ID%' in ids)"`) do set "LIST_HAS_OPERATION=%%t"
if /i not "%LIST_HAS_OPERATION%"=="True" (
  echo [FAIL] seeded operation is missing from client operations list
  goto :fail
)

echo [5/7] Load operation detail...
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/operations/%OPERATION_ID%" "%CLIENT_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=str(data.get('id') or '') == '%OPERATION_ID%' and str(data.get('status') or '').upper() == 'DECLINED' and bool(str(data.get('reason') or '').strip()); print(ok)"`) do set "DETAIL_OK=%%t"
if /i not "%DETAIL_OK%"=="True" (
  echo [FAIL] operation detail did not return the expected declined payload
  type "%DETAIL_FILE%"
  goto :fail
)

echo [6/7] Load explainability view...
call :http_request "GET" "%CORE_ROOT%/explain?kpi_key=declines_total&window_days=7" "%CLIENT_AUTH_HEADER%" "" "200" "%EXPLAIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%EXPLAIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=str(data.get('id') or '') == 'declines_total' and str(data.get('kind') or '') == 'kpi' and isinstance(data.get('reason_tree'), dict) and isinstance(data.get('evidence'), list) and isinstance(data.get('recommended_actions'), list); print(ok)"`) do set "EXPLAIN_OK=%%t"
if /i not "%EXPLAIN_OK%"=="True" (
  echo [FAIL] explain payload is missing the expected KPI sections
  type "%EXPLAIN_FILE%"
  goto :fail
)

echo [7/7] Operations explain smoke completed.
call :cleanup
exit /b 0

:fail
call :cleanup
echo [SMOKE] Failed.
exit /b 1

:resolve_auth_openapi
set "AUTH_CODE="
for %%u in ("%AUTH_URL%/openapi.json" "%AUTH_HOST_BASE%/openapi.json" "%AUTH_HOST_BASE%/api/auth/openapi.json") do (
  for /f "usebackq tokens=*" %%c in (`curl -s -S -o NUL -w "%%{http_code}" %%~u 2^>nul`) do (
    if "%%c"=="200" (
      set "AUTH_CODE=%%c"
      exit /b 0
    )
  )
)
exit /b 0

:cleanup
del /q "%CLIENT_LOGIN_FILE%" 2>nul
del /q "%CLIENT_LOGIN_BODY%" 2>nul
del /q "%CLIENT_VERIFY_FILE%" 2>nul
del /q "%PORTAL_ME_FILE%" 2>nul
del /q "%LIST_FILE%" 2>nul
del /q "%DETAIL_FILE%" 2>nul
del /q "%EXPLAIN_FILE%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
del /q "%SEED_SQL_FILE%" 2>nul
del /q "%SEED_LOG%" 2>nul
exit /b 0

:wait_for_status
set "WAIT_URL=%~1"
set "WAIT_EXPECTED=%~2"
set "WAIT_ATTEMPTS=%~3"
set "WAIT_DELAY=%~4"
if "%WAIT_ATTEMPTS%"=="" set "WAIT_ATTEMPTS=15"
if "%WAIT_DELAY%"=="" set "WAIT_DELAY=2"
set "WAIT_CODE="
for /l %%i in (1,1,%WAIT_ATTEMPTS%) do (
  for /f "usebackq tokens=*" %%c in (`curl -s -S -o NUL -w "%%{http_code}" "%WAIT_URL%" 2^>nul`) do (
    set "WAIT_CODE=%%c"
    if "%%c"=="%WAIT_EXPECTED%" exit /b 0
  )
  if not "%%i"=="%WAIT_ATTEMPTS%" powershell -NoProfile -Command "Start-Sleep -Seconds %WAIT_DELAY%" >nul
)
echo [FAIL] %WAIT_URL% did not reach %WAIT_EXPECTED%, last code=%WAIT_CODE%
exit /b 1

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\ops_resp_%RANDOM%.json"
if "%BODY_FILE%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
)
if "%CODE%"=="" exit /b 1
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if defined MATCHED exit /b 0
echo [FAIL] %METHOD% %URL% expected %EXPECTED% got %CODE%
if exist "%OUT%" type "%OUT%"
exit /b 1
