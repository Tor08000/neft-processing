@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "ADMIN_ROOT=%CORE_API_BASE%/api/v1/admin"
set "SMOKE_UNIQ=%RANDOM%%RANDOM%"

set "LOGIN_FILE=%TEMP%\ops_dispute_login_%RANDOM%.json"
set "LOGIN_BODY_FILE=%TEMP%\ops_dispute_login_body_%RANDOM%.json"
set "VERIFY_FILE=%TEMP%\ops_dispute_verify_%RANDOM%.txt"
set "CORE_HEALTH_FILE=%TEMP%\ops_dispute_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\ops_dispute_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\ops_dispute_seed_%RANDOM%.log"
set "OPEN_BODY_FILE=%TEMP%\ops_dispute_open_body_%RANDOM%.json"
set "OPEN_FILE=%TEMP%\ops_dispute_open_%RANDOM%.json"
set "REVIEW_BODY_FILE=%TEMP%\ops_dispute_review_body_%RANDOM%.json"
set "REVIEW_FILE=%TEMP%\ops_dispute_review_%RANDOM%.json"
set "ACCEPT_BODY_FILE=%TEMP%\ops_dispute_accept_body_%RANDOM%.json"
set "ACCEPT_FILE=%TEMP%\ops_dispute_accept_%RANDOM%.json"
set "REFUND_BODY_FILE=%TEMP%\ops_dispute_refund_body_%RANDOM%.json"
set "REFUND_FILE=%TEMP%\ops_dispute_refund_%RANDOM%.json"
set "VERIFY_SQL_FILE=%TEMP%\ops_dispute_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\ops_dispute_verify_%RANDOM%.log"

set "ADMIN_TOKEN="
set "ADMIN_AUTH_HEADER="
set "DISPUTE_ID="
set "REFUND_ID="
for /f "usebackq tokens=1,2 delims==" %%a in (`python -c "import uuid; uniq=uuid.uuid4().hex[:8]; print('SMOKE_DISPUTE_OP_ID=' + str(uuid.uuid4())); print('SMOKE_REFUND_OP_ID=' + str(uuid.uuid4())); print('SMOKE_MERCHANT_ID=' + str(uuid.uuid4())); print('SMOKE_DISPUTE_CLIENT=' + str(uuid.uuid4())); print('SMOKE_REFUND_CLIENT=' + str(uuid.uuid4())); print('SMOKE_DISPUTE_OP_BIZ=smoke-dispute-op-' + uniq); print('SMOKE_REFUND_OP_BIZ=smoke-refund-op-' + uniq); print('SMOKE_DISPUTE_CARD=smoke-dispute-card-' + uniq); print('SMOKE_REFUND_CARD=smoke-refund-card-' + uniq); print('SMOKE_DISPUTE_IDEMPOTENCY=smoke-dispute-' + uniq); print('SMOKE_DISPUTE_ACCEPT_IDEMPOTENCY=smoke-dispute-accept-' + uniq); print('SMOKE_REFUND_IDEMPOTENCY=smoke-refund-' + uniq)"`) do set "%%a=%%b"

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

echo [1/7] Login admin...
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/7] Verify admin auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%VERIFY_FILE%" || goto :fail

echo [3/7] Seed captured operations for dispute + refund...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo INSERT INTO operations ^(id, operation_id, operation_type, status, merchant_id, terminal_id, client_id, card_id, amount, currency, captured_amount, refunded_amount, authorized, response_code, response_message^) VALUES
>> "%SEED_SQL_FILE%" echo ^('%SMOKE_DISPUTE_OP_ID%', '%SMOKE_DISPUTE_OP_BIZ%', 'CAPTURE', 'CAPTURED', '%SMOKE_MERCHANT_ID%', 'terminal-smoke', '%SMOKE_DISPUTE_CLIENT%', '%SMOKE_DISPUTE_CARD%', 200, 'RUB', 200, 0, TRUE, '00', 'OK'^),
>> "%SEED_SQL_FILE%" echo ^('%SMOKE_REFUND_OP_ID%', '%SMOKE_REFUND_OP_BIZ%', 'CAPTURE', 'CAPTURED', '%SMOKE_MERCHANT_ID%', 'terminal-smoke', '%SMOKE_REFUND_CLIENT%', '%SMOKE_REFUND_CARD%', 120, 'RUB', 120, 0, TRUE, '00', 'OK'^);
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] dispute/refund seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/7] Open -> review -> accept dispute...
python -c "import json; from pathlib import Path; Path(r'%OPEN_BODY_FILE%').write_text(json.dumps({'operation_id': r'%SMOKE_DISPUTE_OP_ID%', 'amount': 80, 'fee_amount': 10, 'initiator': 'smoke-admin', 'place_hold': True, 'idempotency_key': r'%SMOKE_DISPUTE_IDEMPOTENCY%'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/disputes/open" "%ADMIN_AUTH_HEADER%" "%OPEN_BODY_FILE%" "200" "%OPEN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%OPEN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "DISPUTE_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%OPEN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=bool(data.get('id')) and str(data.get('status') or '') == 'OPEN' and bool(data.get('hold_posting_id')); print(ok)"`) do set "OPEN_OK=%%t"
if "%DISPUTE_ID%"=="" (
  echo [FAIL] dispute open response missing id
  type "%OPEN_FILE%"
  goto :fail
)
if /i not "%OPEN_OK%"=="True" (
  echo [FAIL] dispute open response missing OPEN status or hold posting
  type "%OPEN_FILE%"
  goto :fail
)
python -c "import json; from pathlib import Path; Path(r'%REVIEW_BODY_FILE%').write_text(json.dumps({'initiator': 'smoke-admin'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/disputes/%DISPUTE_ID%/review" "%ADMIN_AUTH_HEADER%" "%REVIEW_BODY_FILE%" "200" "%REVIEW_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REVIEW_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '') == 'UNDER_REVIEW')"`) do set "REVIEW_OK=%%t"
if /i not "%REVIEW_OK%"=="True" (
  echo [FAIL] dispute review response missing UNDER_REVIEW status
  type "%REVIEW_FILE%"
  goto :fail
)
python -c "import json; from pathlib import Path; Path(r'%ACCEPT_BODY_FILE%').write_text(json.dumps({'initiator': 'smoke-admin', 'idempotency_key': r'%SMOKE_DISPUTE_ACCEPT_IDEMPOTENCY%', 'settlement_closed': False}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/disputes/%DISPUTE_ID%/accept" "%ADMIN_AUTH_HEADER%" "%ACCEPT_BODY_FILE%" "200" "%ACCEPT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ACCEPT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=str(data.get('status') or '') == 'ACCEPTED' and bool(data.get('hold_posting_id')) and bool(data.get('resolution_posting_id')); print(ok)"`) do set "ACCEPT_OK=%%t"
if /i not "%ACCEPT_OK%"=="True" (
  echo [FAIL] dispute accept response missing ACCEPTED status or posting ids
  type "%ACCEPT_FILE%"
  goto :fail
)

echo [5/7] Create refund...
python -c "import json; from pathlib import Path; Path(r'%REFUND_BODY_FILE%').write_text(json.dumps({'operation_id': r'%SMOKE_REFUND_OP_ID%', 'amount': 30, 'reason': 'smoke-refund', 'initiator': 'smoke-admin', 'idempotency_key': r'%SMOKE_REFUND_IDEMPOTENCY%', 'settlement_closed': False}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_ROOT%/refunds" "%ADMIN_AUTH_HEADER%" "%REFUND_BODY_FILE%" "200" "%REFUND_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REFUND_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "REFUND_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REFUND_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=bool(data.get('id')) and str(data.get('status') or '') == 'POSTED' and str(data.get('settlement_policy') or '') == 'SAME_PERIOD' and bool(data.get('posting_id')); print(ok)"`) do set "REFUND_OK=%%t"
if "%REFUND_ID%"=="" (
  echo [FAIL] refund response missing id
  type "%REFUND_FILE%"
  goto :fail
)
if /i not "%REFUND_OK%"=="True" (
  echo [FAIL] refund response missing POSTED / SAME_PERIOD / posting_id truth
  type "%REFUND_FILE%"
  goto :fail
)

echo [6/7] Verify persisted dispute/refund rows...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_STATUS=' ^|^| status::text FROM disputes WHERE id = '%DISPUTE_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_HOLD_PLACED=' ^|^| hold_placed::text FROM disputes WHERE id = '%DISPUTE_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_HOLD_POSTING=' ^|^| COALESCE^(hold_posting_id::text, ''^) FROM disputes WHERE id = '%DISPUTE_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_RESOLUTION_POSTING=' ^|^| COALESCE^(resolution_posting_id::text, ''^) FROM disputes WHERE id = '%DISPUTE_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_EVENT_OPENED=' ^|^| count^(*^)::text FROM dispute_events WHERE dispute_id = '%DISPUTE_ID%' AND event_type = 'OPENED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_EVENT_HOLD=' ^|^| count^(*^)::text FROM dispute_events WHERE dispute_id = '%DISPUTE_ID%' AND event_type = 'HOLD_PLACED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_EVENT_REVIEW=' ^|^| count^(*^)::text FROM dispute_events WHERE dispute_id = '%DISPUTE_ID%' AND event_type = 'MOVED_TO_REVIEW';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_EVENT_ACCEPTED=' ^|^| count^(*^)::text FROM dispute_events WHERE dispute_id = '%DISPUTE_ID%' AND event_type = 'ACCEPTED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_EVENT_REFUND=' ^|^| count^(*^)::text FROM dispute_events WHERE dispute_id = '%DISPUTE_ID%' AND event_type = 'REFUND_POSTED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_EVENT_FEE=' ^|^| count^(*^)::text FROM dispute_events WHERE dispute_id = '%DISPUTE_ID%' AND event_type = 'FEE_POSTED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_POSTING_HOLD=' ^|^| count^(*^)::text FROM posting_batches WHERE operation_id = '%SMOKE_DISPUTE_OP_ID%' AND posting_type = 'DISPUTE_HOLD';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_POSTING_REFUND=' ^|^| count^(*^)::text FROM posting_batches WHERE operation_id = '%SMOKE_DISPUTE_OP_ID%' AND posting_type = 'REFUND';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISPUTE_POSTING_ADJUSTMENT=' ^|^| count^(*^)::text FROM posting_batches WHERE operation_id = '%SMOKE_DISPUTE_OP_ID%' AND posting_type = 'ADJUSTMENT';
>> "%VERIFY_SQL_FILE%" echo SELECT 'REFUND_STATUS=' ^|^| status::text FROM refund_requests WHERE id = '%REFUND_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'REFUND_POLICY=' ^|^| settlement_policy::text FROM refund_requests WHERE id = '%REFUND_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'REFUND_POSTING=' ^|^| COALESCE^(posted_posting_id::text, ''^) FROM refund_requests WHERE id = '%REFUND_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'REFUND_POSTING_REFUND=' ^|^| count^(*^)::text FROM posting_batches WHERE operation_id = '%SMOKE_REFUND_OP_ID%' AND posting_type = 'REFUND';
>> "%VERIFY_SQL_FILE%" echo SELECT 'REFUND_OPERATION_TOTAL=' ^|^| refunded_amount::text FROM operations WHERE id = '%SMOKE_REFUND_OP_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] dispute/refund verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_STATUS=ACCEPTED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute status is not ACCEPTED
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"DISPUTE_HOLD_PLACED=[Ff]alse" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute hold flag was not released after acceptance
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"DISPUTE_HOLD_POSTING=." "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute hold posting id missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"DISPUTE_RESOLUTION_POSTING=." "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute resolution posting id missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_EVENT_OPENED=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute OPENED event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_EVENT_HOLD=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute HOLD_PLACED event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_EVENT_REVIEW=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute MOVED_TO_REVIEW event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_EVENT_ACCEPTED=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute ACCEPTED event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_EVENT_REFUND=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute REFUND_POSTED event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_EVENT_FEE=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute FEE_POSTED event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_POSTING_HOLD=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute hold posting batch missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_POSTING_REFUND=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute refund posting batch missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISPUTE_POSTING_ADJUSTMENT=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] dispute fee adjustment posting batch missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"REFUND_STATUS=POSTED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] refund row is not POSTED
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"REFUND_POLICY=SAME_PERIOD" "%VERIFY_LOG%" >nul || (
  echo [FAIL] refund settlement policy is not SAME_PERIOD
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"REFUND_POSTING=." "%VERIFY_LOG%" >nul || (
  echo [FAIL] refund posting id missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"REFUND_POSTING_REFUND=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] refund posting batch missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"REFUND_OPERATION_TOTAL=30" "%VERIFY_LOG%" >nul || (
  echo [FAIL] refunded_amount on refund operation is not 30
  type "%VERIFY_LOG%"
  goto :fail
)

echo [SMOKE] Dispute / refund smoke completed.
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
del /q "%LOGIN_FILE%" 2>nul
del /q "%LOGIN_BODY_FILE%" 2>nul
del /q "%VERIFY_FILE%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
del /q "%SEED_SQL_FILE%" 2>nul
del /q "%SEED_LOG%" 2>nul
del /q "%OPEN_BODY_FILE%" 2>nul
del /q "%OPEN_FILE%" 2>nul
del /q "%REVIEW_BODY_FILE%" 2>nul
del /q "%REVIEW_FILE%" 2>nul
del /q "%ACCEPT_BODY_FILE%" 2>nul
del /q "%ACCEPT_FILE%" 2>nul
del /q "%REFUND_BODY_FILE%" 2>nul
del /q "%REFUND_FILE%" 2>nul
del /q "%VERIFY_SQL_FILE%" 2>nul
del /q "%VERIFY_LOG%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\ops_dispute_resp_%RANDOM%.json"
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
