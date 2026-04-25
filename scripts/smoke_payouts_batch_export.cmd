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
set "SMOKE_DATE=2026-01-15"
set "SMOKE_PARTNER_ID=smoke-partner-payout-export"
set "SMOKE_PERIOD_ID=10000000-0000-0000-0000-00000000aa11"
set "SMOKE_EXTERNAL_REF=SMOKE-PAYOUT-EXPORT-001"
set "ABAC_VERSION_ID=10000000-0000-0000-0000-00000000aa12"
set "ABAC_POLICY_ID=10000000-0000-0000-0000-00000000aa13"

set "LOGIN_FILE=%TEMP%\payouts_login_%RANDOM%.json"
set "LOGIN_BODY_FILE=%TEMP%\payouts_login_body_%RANDOM%.json"
set "VERIFY_FILE=%TEMP%\payouts_verify_%RANDOM%.txt"
set "CORE_HEALTH_FILE=%TEMP%\payouts_core_health_%RANDOM%.json"
set "CLOSE_BODY_FILE=%TEMP%\payouts_close_body_%RANDOM%.json"
set "CLOSE_FILE=%TEMP%\payouts_close_%RANDOM%.json"
set "LIST_FILE=%TEMP%\payouts_list_%RANDOM%.json"
set "DETAIL_FILE=%TEMP%\payouts_detail_%RANDOM%.json"
set "EXPORT_BODY_FILE=%TEMP%\payouts_export_body_%RANDOM%.json"
set "EXPORT_FILE=%TEMP%\payouts_export_%RANDOM%.json"
set "EXPORT_LIST_FILE=%TEMP%\payouts_export_list_%RANDOM%.json"
set "DOWNLOAD_FILE=%TEMP%\payouts_download_%RANDOM%.csv"
set "SEED_SQL_FILE=%TEMP%\payouts_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\payouts_seed_%RANDOM%.log"
set "VERIFY_SQL_FILE=%TEMP%\payouts_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\payouts_verify_%RANDOM%.log"

set "ADMIN_TOKEN="
set "ADMIN_AUTH_HEADER="
set "BATCH_ID="
set "EXPORT_ID="

echo [0/9] Check docker compose postgres + minio...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)
docker compose ps minio >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose minio unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/9] Check auth + core surfaces...
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

echo [1/9] Login admin...
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/9] Verify admin auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%VERIFY_FILE%" || goto :fail

echo [3/9] Seed dedicated payout slice...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo DELETE FROM payout_export_files WHERE batch_id IN ^(SELECT id FROM payout_batches WHERE partner_id = '%SMOKE_PARTNER_ID%' AND date_from = DATE '%SMOKE_DATE%' AND date_to = DATE '%SMOKE_DATE%'^);
>> "%SEED_SQL_FILE%" echo DELETE FROM payout_items WHERE batch_id IN ^(SELECT id FROM payout_batches WHERE partner_id = '%SMOKE_PARTNER_ID%' AND date_from = DATE '%SMOKE_DATE%' AND date_to = DATE '%SMOKE_DATE%'^);
>> "%SEED_SQL_FILE%" echo DELETE FROM payout_batches WHERE partner_id = '%SMOKE_PARTNER_ID%' AND date_from = DATE '%SMOKE_DATE%' AND date_to = DATE '%SMOKE_DATE%';
>> "%SEED_SQL_FILE%" echo DELETE FROM operations WHERE operation_id LIKE 'smoke-payout-export-%%';
>> "%SEED_SQL_FILE%" echo DELETE FROM billing_periods WHERE period_type = 'ADHOC' AND start_at = TIMESTAMPTZ '%SMOKE_DATE% 00:00:00+00' AND end_at = TIMESTAMPTZ '%SMOKE_DATE% 23:59:59.999999+00';
>> "%SEED_SQL_FILE%" echo INSERT INTO billing_periods ^(id, period_type, start_at, end_at, tz, status, finalized_at^) VALUES ^('%SMOKE_PERIOD_ID%', 'ADHOC', TIMESTAMPTZ '%SMOKE_DATE% 00:00:00+00', TIMESTAMPTZ '%SMOKE_DATE% 23:59:59.999999+00', 'UTC', 'FINALIZED', timezone^('utc', now^(^)^)^);
>> "%SEED_SQL_FILE%" echo WITH active_abac_version AS ^(
>> "%SEED_SQL_FILE%" echo   SELECT id
>> "%SEED_SQL_FILE%" echo   FROM abac_policy_versions
>> "%SEED_SQL_FILE%" echo   WHERE status = 'ACTIVE'
>> "%SEED_SQL_FILE%" echo   ORDER BY activated_at DESC NULLS LAST, created_at DESC NULLS LAST
>> "%SEED_SQL_FILE%" echo   LIMIT 1
>> "%SEED_SQL_FILE%" echo ^), ensured_abac_version AS ^(
>> "%SEED_SQL_FILE%" echo   INSERT INTO abac_policy_versions ^(id, name, status, created_at, published_at, activated_at, created_by^)
>> "%SEED_SQL_FILE%" echo   SELECT '%ABAC_VERSION_ID%', 'payout-export-smoke-default', 'ACTIVE', timezone^('utc', now^(^)^), timezone^('utc', now^(^)^), timezone^('utc', now^(^)^), 'smoke_payouts_batch_export'
>> "%SEED_SQL_FILE%" echo   WHERE NOT EXISTS ^(SELECT 1 FROM active_abac_version^)
>> "%SEED_SQL_FILE%" echo   ON CONFLICT ^(id^) DO UPDATE SET status = 'ACTIVE', published_at = EXCLUDED.published_at, activated_at = EXCLUDED.activated_at, created_by = EXCLUDED.created_by
>> "%SEED_SQL_FILE%" echo   RETURNING id
>> "%SEED_SQL_FILE%" echo ^), chosen_abac_version AS ^(
>> "%SEED_SQL_FILE%" echo   SELECT id FROM active_abac_version
>> "%SEED_SQL_FILE%" echo   UNION ALL
>> "%SEED_SQL_FILE%" echo   SELECT id FROM ensured_abac_version
>> "%SEED_SQL_FILE%" echo ^)
>> "%SEED_SQL_FILE%" echo INSERT INTO abac_policies ^(id, version_id, code, effect, priority, actions, resource_type, condition, reason_code, created_at^)
>> "%SEED_SQL_FILE%" echo SELECT '%ABAC_POLICY_ID%', id, 'payout_export_admin_allow', 'ALLOW', 100, '["payouts:export"]'::jsonb, 'PAYOUT_BATCH', '{"all":[{"eq":["principal.type","USER"]},{"any":[{"contains":["principal.roles","ADMIN_FINANCE"]},{"contains":["principal.roles","SUPERADMIN"]}]}]}'::jsonb, 'PAYOUT_EXPORT_ADMIN', timezone^('utc', now^(^)^)
>> "%SEED_SQL_FILE%" echo FROM chosen_abac_version
>> "%SEED_SQL_FILE%" echo LIMIT 1
>> "%SEED_SQL_FILE%" echo ON CONFLICT ON CONSTRAINT uq_abac_policy_version_code DO UPDATE SET effect = EXCLUDED.effect, priority = EXCLUDED.priority, actions = EXCLUDED.actions, resource_type = EXCLUDED.resource_type, condition = EXCLUDED.condition, reason_code = EXCLUDED.reason_code;
>> "%SEED_SQL_FILE%" echo INSERT INTO operations ^(id, operation_id, operation_type, status, created_at, updated_at, merchant_id, terminal_id, client_id, card_id, product_id, amount, amount_settled, currency, quantity, captured_amount, refunded_amount, response_code, response_message, authorized^) VALUES
>> "%SEED_SQL_FILE%" echo ^('10000000-0000-0000-0000-00000000bb01', 'smoke-payout-export-001', 'COMMIT', 'CAPTURED', TIMESTAMPTZ '%SMOKE_DATE% 01:00:00+00', TIMESTAMPTZ '%SMOKE_DATE% 01:00:00+00', '%SMOKE_PARTNER_ID%', 'terminal-smoke-1', 'client-smoke-1', 'card-smoke-1', 'FUEL', 1000, 1000, 'RUB', 1.000, 1000, 0, '00', 'OK', TRUE^),
>> "%SEED_SQL_FILE%" echo ^('10000000-0000-0000-0000-00000000bb02', 'smoke-payout-export-002', 'COMMIT', 'CAPTURED', TIMESTAMPTZ '%SMOKE_DATE% 02:00:00+00', TIMESTAMPTZ '%SMOKE_DATE% 02:00:00+00', '%SMOKE_PARTNER_ID%', 'terminal-smoke-1', 'client-smoke-2', 'card-smoke-2', 'FUEL', 1100, 1100, 'RUB', 1.000, 1100, 0, '00', 'OK', TRUE^),
>> "%SEED_SQL_FILE%" echo ^('10000000-0000-0000-0000-00000000bb03', 'smoke-payout-export-003', 'COMMIT', 'CAPTURED', TIMESTAMPTZ '%SMOKE_DATE% 03:00:00+00', TIMESTAMPTZ '%SMOKE_DATE% 03:00:00+00', '%SMOKE_PARTNER_ID%', 'terminal-smoke-1', 'client-smoke-3', 'card-smoke-3', 'FUEL', 1200, 1200, 'RUB', 1.000, 1200, 0, '00', 'OK', TRUE^);
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] payout seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/9] Close payout period...
python -c "import json; from pathlib import Path; Path(r'%CLOSE_BODY_FILE%').write_text(json.dumps({'tenant_id': 1, 'partner_id': r'%SMOKE_PARTNER_ID%', 'date_from': r'%SMOKE_DATE%', 'date_to': r'%SMOKE_DATE%'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/payouts/close-period" "%ADMIN_AUTH_HEADER%" "%CLOSE_BODY_FILE%" "200" "%CLOSE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLOSE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('batch_id',''))"`) do set "BATCH_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLOSE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=bool(data.get('batch_id')) and str(data.get('state') or '') == 'READY' and str(data.get('total_amount') or '') in {'3300.00','3300'} and int(data.get('operations_count') or 0) == 3 and int(data.get('items_count') or 0) == 1; print(ok)"`) do set "CLOSE_OK=%%t"
if "%BATCH_ID%"=="" (
  echo [FAIL] payout close-period missing batch_id
  type "%CLOSE_FILE%"
  goto :fail
)
if /i not "%CLOSE_OK%"=="True" (
  echo [FAIL] payout close-period response did not match expected READY aggregate
  type "%CLOSE_FILE%"
  goto :fail
)

echo [5/9] Verify batch list and detail...
call :http_request "GET" "%CORE_API_BASE%/api/v1/payouts/batches?partner_id=%SMOKE_PARTNER_ID%&date_from=%SMOKE_DATE%&date_to=%SMOKE_DATE%&limit=10" "%ADMIN_AUTH_HEADER%" "" "200" "%LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=payload.get('items') or []; ok=payload.get('total') == 1 and bool(items) and str(items[0].get('batch_id') or '') == r'%BATCH_ID%'; print(ok)"`) do set "LIST_OK=%%t"
if /i not "%LIST_OK%"=="True" (
  echo [FAIL] payout batch list did not return the seeded batch
  type "%LIST_FILE%"
  goto :fail
)
call :http_request "GET" "%CORE_API_BASE%/api/v1/payouts/batches/%BATCH_ID%" "%ADMIN_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=str(data.get('id') or '') == r'%BATCH_ID%' and str(data.get('partner_id') or '') == r'%SMOKE_PARTNER_ID%' and str(data.get('state') or '') == 'READY' and int(data.get('operations_count') or 0) == 3 and len(data.get('items') or []) == 1; print(ok)"`) do set "DETAIL_OK=%%t"
if /i not "%DETAIL_OK%"=="True" (
  echo [FAIL] payout batch detail did not reflect the seeded aggregate
  type "%DETAIL_FILE%"
  goto :fail
)

echo [6/9] Create and list payout export...
python -c "import json; from pathlib import Path; Path(r'%EXPORT_BODY_FILE%').write_text(json.dumps({'format':'CSV','provider':'bank','external_ref':r'%SMOKE_EXTERNAL_REF%'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/payouts/batches/%BATCH_ID%/export" "%ADMIN_AUTH_HEADER%" "%EXPORT_BODY_FILE%" "200" "%EXPORT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%EXPORT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('export_id',''))"`) do set "EXPORT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%EXPORT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=bool(data.get('export_id')) and str(data.get('batch_id') or '') == r'%BATCH_ID%' and str(data.get('state') or '') == 'UPLOADED' and str(data.get('format') or '') == 'CSV' and str(data.get('external_ref') or '') == r'%SMOKE_EXTERNAL_REF%'; print(ok)"`) do set "EXPORT_OK=%%t"
if "%EXPORT_ID%"=="" (
  echo [FAIL] payout export response missing export_id
  type "%EXPORT_FILE%"
  goto :fail
)
if /i not "%EXPORT_OK%"=="True" (
  echo [FAIL] payout export response did not match expected UPLOADED CSV shape
  type "%EXPORT_FILE%"
  goto :fail
)
call :http_request "GET" "%CORE_API_BASE%/api/v1/payouts/batches/%BATCH_ID%/exports" "%ADMIN_AUTH_HEADER%" "" "200" "%EXPORT_LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%EXPORT_LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=payload.get('items') or []; ok=bool(items) and str(items[0].get('export_id') or '') == r'%EXPORT_ID%'; print(ok)"`) do set "EXPORT_LIST_OK=%%t"
if /i not "%EXPORT_LIST_OK%"=="True" (
  echo [FAIL] payout export list did not return the generated export
  type "%EXPORT_LIST_FILE%"
  goto :fail
)

echo [7/9] Download payout export...
call :http_request "GET" "%CORE_API_BASE%/api/v1/payouts/exports/%EXPORT_ID%/download" "%ADMIN_AUTH_HEADER%" "" "200" "%DOWNLOAD_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "from pathlib import Path; payload=Path(r'%DOWNLOAD_FILE%').read_bytes(); ok=(b'Batch ID' in payload and b'%SMOKE_PARTNER_ID%' in payload and b'Total amount (net)' in payload and b'3300.00' in payload and b'item_id' in payload); print(ok)"`) do set "DOWNLOAD_OK=%%t"
if /i not "%DOWNLOAD_OK%"=="True" (
  echo [FAIL] downloaded payout export file is missing expected CSV content
  goto :fail
)

echo [8/9] Verify persisted payout/export rows...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'BATCH_COUNT=' ^|^| count^(*^)::text FROM payout_batches WHERE partner_id = '%SMOKE_PARTNER_ID%' AND date_from = DATE '%SMOKE_DATE%' AND date_to = DATE '%SMOKE_DATE%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'BATCH_STATE=' ^|^| state::text FROM payout_batches WHERE id = '%BATCH_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'BATCH_AMOUNT=' ^|^| total_amount::text FROM payout_batches WHERE id = '%BATCH_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'BATCH_OPS=' ^|^| operations_count::text FROM payout_batches WHERE id = '%BATCH_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'EXPORT_COUNT=' ^|^| count^(*^)::text FROM payout_export_files WHERE batch_id = '%BATCH_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'EXPORT_STATE=' ^|^| state::text FROM payout_export_files WHERE id = '%EXPORT_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'EXPORT_FORMAT=' ^|^| format::text FROM payout_export_files WHERE id = '%EXPORT_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'EXPORT_REF=' ^|^| COALESCE^(external_ref, ''^) FROM payout_export_files WHERE id = '%EXPORT_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] payout verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"BATCH_COUNT=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout batch count is not 1
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"BATCH_STATE=READY" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout batch state is not READY
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"BATCH_AMOUNT=3300.00" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout batch total_amount is not 3300.00
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"BATCH_OPS=3" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout batch operations_count is not 3
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"EXPORT_COUNT=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout export count is not 1
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"EXPORT_STATE=UPLOADED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout export state is not UPLOADED
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"EXPORT_FORMAT=CSV" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout export format is not CSV
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"EXPORT_REF=%SMOKE_EXTERNAL_REF%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted payout export external_ref mismatch
  type "%VERIFY_LOG%"
  goto :fail
)

echo [9/9] Payout export smoke completed.
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
del /q "%CLOSE_BODY_FILE%" 2>nul
del /q "%CLOSE_FILE%" 2>nul
del /q "%LIST_FILE%" 2>nul
del /q "%DETAIL_FILE%" 2>nul
del /q "%EXPORT_BODY_FILE%" 2>nul
del /q "%EXPORT_FILE%" 2>nul
del /q "%EXPORT_LIST_FILE%" 2>nul
del /q "%DOWNLOAD_FILE%" 2>nul
del /q "%SEED_SQL_FILE%" 2>nul
del /q "%SEED_LOG%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\payouts_resp_%RANDOM%.json"
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
