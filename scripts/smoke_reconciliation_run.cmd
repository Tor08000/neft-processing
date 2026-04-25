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
set "RECON_ROOT=%CORE_API_BASE%/api/core/v1/admin/reconciliation"
set "SMOKE_UNIQ=%RANDOM%%RANDOM%"
set "SMOKE_PROVIDER=bank_smoke"
set "SMOKE_IDEMPOTENCY_KEY=smoke-reconciliation-%SMOKE_UNIQ%"
set "SMOKE_LINE_REF=smoke-line-%SMOKE_UNIQ%"

set "LOGIN_FILE=%TEMP%\recon_login_%RANDOM%.json"
set "LOGIN_BODY_FILE=%TEMP%\recon_login_body_%RANDOM%.json"
set "VERIFY_FILE=%TEMP%\recon_verify_%RANDOM%.txt"
set "CORE_HEALTH_FILE=%TEMP%\recon_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\recon_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\recon_seed_%RANDOM%.log"
set "STATEMENT_BODY_FILE=%TEMP%\recon_statement_body_%RANDOM%.json"
set "STATEMENT_FILE=%TEMP%\recon_statement_%RANDOM%.json"
set "RUN_BODY_FILE=%TEMP%\recon_run_body_%RANDOM%.json"
set "RUN_FILE=%TEMP%\recon_run_%RANDOM%.json"
set "RUN_DETAIL_FILE=%TEMP%\recon_run_detail_%RANDOM%.json"
set "DISCREPANCIES_FILE=%TEMP%\recon_discrepancies_%RANDOM%.json"
set "EXPORT_FILE=%TEMP%\recon_export_%RANDOM%.csv"
set "VERIFY_SQL_FILE=%TEMP%\recon_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\recon_verify_%RANDOM%.log"

set "ADMIN_TOKEN="
set "ADMIN_AUTH_HEADER="
set "STATEMENT_ID="
set "RUN_ID="
for /f "usebackq tokens=1,2 delims==" %%a in (`python -c "from datetime import datetime, timedelta, timezone; import uuid; seed=uuid.uuid4().int; uniq=uuid.uuid4().hex[:8]; start=datetime(2031, 2, (seed %% 27) + 1, (seed >> 8) %% 24, (seed >> 16) %% 55, 0, tzinfo=timezone.utc); end=start + timedelta(minutes=4, seconds=59); print('SMOKE_CLIENT_ID=smoke-recon-client-' + uniq); print('SMOKE_CLIENT_AR_ACCOUNT_ID=' + str(uuid.uuid4())); print('SMOKE_SUSPENSE_ACCOUNT_ID=' + str(uuid.uuid4())); print('SMOKE_TX_ID=' + str(uuid.uuid4())); print('SMOKE_DEBIT_ENTRY_ID=' + str(uuid.uuid4())); print('SMOKE_CREDIT_ENTRY_ID=' + str(uuid.uuid4())); print('SMOKE_PERIOD_FROM=' + start.isoformat()); print('SMOKE_PERIOD_TO=' + end.isoformat())"`) do set "%%a=%%b"

echo [0/8] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/8] Check auth + core surfaces...
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

echo [1/8] Login admin...
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/8] Verify admin auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%VERIFY_FILE%" || goto :fail

echo [3/8] Seed dedicated internal ledger slice...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo INSERT INTO internal_ledger_accounts ^(id, tenant_id, client_id, account_type, currency, status^)
>> "%SEED_SQL_FILE%" echo VALUES ^('%SMOKE_SUSPENSE_ACCOUNT_ID%', 1, NULL, 'SUSPENSE', 'RUB', 'ACTIVE'^)
>> "%SEED_SQL_FILE%" echo ON CONFLICT ON CONSTRAINT uq_internal_ledger_accounts_scope DO UPDATE SET status = EXCLUDED.status;
>> "%SEED_SQL_FILE%" echo INSERT INTO internal_ledger_accounts ^(id, tenant_id, client_id, account_type, currency, status^)
>> "%SEED_SQL_FILE%" echo VALUES ^('%SMOKE_CLIENT_AR_ACCOUNT_ID%', 1, '%SMOKE_CLIENT_ID%', 'CLIENT_AR', 'RUB', 'ACTIVE'^);
>> "%SEED_SQL_FILE%" echo INSERT INTO internal_ledger_transactions ^(id, tenant_id, transaction_type, external_ref_type, external_ref_id, idempotency_key, total_amount, total_debit, total_credit, currency, batch_sequence, previous_batch_hash, batch_hash, posted_at, meta^)
>> "%SEED_SQL_FILE%" echo VALUES ^(
>> "%SEED_SQL_FILE%" echo   '%SMOKE_TX_ID%',
>> "%SEED_SQL_FILE%" echo   1,
>> "%SEED_SQL_FILE%" echo   'ACCOUNTING_EXPORT_CONFIRMED',
>> "%SEED_SQL_FILE%" echo   'SMOKE_RECONCILIATION',
>> "%SEED_SQL_FILE%" echo   '%SMOKE_UNIQ%',
>> "%SEED_SQL_FILE%" echo   '%SMOKE_IDEMPOTENCY_KEY%',
>> "%SEED_SQL_FILE%" echo   500,
>> "%SEED_SQL_FILE%" echo   500,
>> "%SEED_SQL_FILE%" echo   500,
>> "%SEED_SQL_FILE%" echo   'RUB',
>> "%SEED_SQL_FILE%" echo   ^(SELECT COALESCE^(MAX^(batch_sequence^), 0^) + 1 FROM internal_ledger_transactions WHERE tenant_id = 1^),
>> "%SEED_SQL_FILE%" echo   ^(SELECT COALESCE^((SELECT batch_hash FROM internal_ledger_transactions WHERE tenant_id = 1 ORDER BY batch_sequence DESC LIMIT 1^), 'GENESIS_INTERNAL_LEDGER_V1'^)^),
>> "%SEED_SQL_FILE%" echo   'SMOKE_RECON_BATCH_%SMOKE_UNIQ%',
>> "%SEED_SQL_FILE%" echo   TIMESTAMPTZ '%SMOKE_PERIOD_FROM%',
>> "%SEED_SQL_FILE%" echo   '{"smoke":"reconciliation_run","balance_after":500}'::jsonb
>> "%SEED_SQL_FILE%" echo ^);
>> "%SEED_SQL_FILE%" echo INSERT INTO internal_ledger_entries ^(id, tenant_id, ledger_transaction_id, account_id, direction, amount, currency, entry_hash, created_at, meta^)
>> "%SEED_SQL_FILE%" echo VALUES
>> "%SEED_SQL_FILE%" echo ^('%SMOKE_DEBIT_ENTRY_ID%', 1, '%SMOKE_TX_ID%', '%SMOKE_CLIENT_AR_ACCOUNT_ID%', 'DEBIT', 500, 'RUB', 'smoke-recon-debit-%SMOKE_UNIQ%', TIMESTAMPTZ '%SMOKE_PERIOD_FROM%', '{"balance_after":500}'::jsonb^),
>> "%SEED_SQL_FILE%" echo ^('%SMOKE_CREDIT_ENTRY_ID%', 1, '%SMOKE_TX_ID%', ^(SELECT id FROM internal_ledger_accounts WHERE tenant_id = 1 AND client_id IS NULL AND account_type = 'SUSPENSE' AND currency = 'RUB' LIMIT 1^), 'CREDIT', 500, 'RUB', 'smoke-recon-credit-%SMOKE_UNIQ%', TIMESTAMPTZ '%SMOKE_PERIOD_FROM%', '{}'::jsonb^);
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] reconciliation seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/8] Upload external statement...
python -c "import json; from pathlib import Path; Path(r'%STATEMENT_BODY_FILE%').write_text(json.dumps({'provider': r'%SMOKE_PROVIDER%', 'period_start': r'%SMOKE_PERIOD_FROM%', 'period_end': r'%SMOKE_PERIOD_TO%', 'currency': 'RUB', 'total_in': '500.0000', 'total_out': '450.0000', 'closing_balance': '50.0000', 'lines': [{'id': r'%SMOKE_LINE_REF%', 'ref': r'%SMOKE_LINE_REF%', 'amount': '500.0000', 'direction': 'IN', 'timestamp': r'%SMOKE_PERIOD_FROM%'}]}), encoding='utf-8')"
call :http_request "POST" "%RECON_ROOT%/external/statements" "%ADMIN_AUTH_HEADER%" "%STATEMENT_BODY_FILE%" "201" "%STATEMENT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%STATEMENT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "STATEMENT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%STATEMENT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=bool(data.get('id')) and str(data.get('provider') or '') == r'%SMOKE_PROVIDER%' and str(data.get('currency') or '') == 'RUB'; print(ok)"`) do set "STATEMENT_OK=%%t"
if "%STATEMENT_ID%"=="" (
  echo [FAIL] external statement response missing id
  type "%STATEMENT_FILE%"
  goto :fail
)
if /i not "%STATEMENT_OK%"=="True" (
  echo [FAIL] external statement response did not match expected provider/currency shape
  type "%STATEMENT_FILE%"
  goto :fail
)

echo [5/8] Run canonical external reconciliation...
python -c "import json; from pathlib import Path; Path(r'%RUN_BODY_FILE%').write_text(json.dumps({'statement_id': r'%STATEMENT_ID%'}), encoding='utf-8')"
call :http_request "POST" "%RECON_ROOT%/external/run" "%ADMIN_AUTH_HEADER%" "%RUN_BODY_FILE%" "201" "%RUN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RUN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "RUN_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RUN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); summary=data.get('summary') or {}; ok=bool(data.get('id')) and str(data.get('scope') or '') == 'external' and str(data.get('status') or '') == 'completed' and str(summary.get('statement_id') or '') == r'%STATEMENT_ID%' and int(summary.get('mismatches_found') or 0) == 3; print(ok)"`) do set "RUN_OK=%%t"
if "%RUN_ID%"=="" (
  echo [FAIL] reconciliation run response missing id
  type "%RUN_FILE%"
  goto :fail
)
if /i not "%RUN_OK%"=="True" (
  echo [FAIL] reconciliation run response did not match expected completed mismatch summary
  type "%RUN_FILE%"
  goto :fail
)

echo [6/8] Verify run detail and discrepancies...
call :http_request "GET" "%RECON_ROOT%/runs/%RUN_ID%" "%ADMIN_AUTH_HEADER%" "" "200" "%RUN_DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RUN_DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); statement=data.get('statement') or {}; timeline=data.get('timeline') or []; ok=str(data.get('id') or '') == r'%RUN_ID%' and str(statement.get('id') or '') == r'%STATEMENT_ID%' and any(str(item.get('event_type') or '') == 'RECONCILIATION_RUN_COMPLETED' for item in timeline); print(ok)"`) do set "RUN_DETAIL_OK=%%t"
if /i not "%RUN_DETAIL_OK%"=="True" (
  echo [FAIL] reconciliation run detail did not expose statement/timeline truth
  type "%RUN_DETAIL_FILE%"
  goto :fail
)
call :http_request "GET" "%RECON_ROOT%/runs/%RUN_ID%/discrepancies" "%ADMIN_AUTH_HEADER%" "" "200" "%DISCREPANCIES_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%DISCREPANCIES_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=payload.get('discrepancies') or []; kinds={str((item.get('details') or {}).get('kind') or '') for item in items if str(item.get('discrepancy_type') or '') == 'balance_mismatch'}; types={str(item.get('discrepancy_type') or '') for item in items}; ok=len(items) == 3 and {'balance_mismatch','unmatched_external'}.issubset(types) and {'total_out','closing_balance'}.issubset(kinds); print(ok)"`) do set "DISCREPANCIES_OK=%%t"
if /i not "%DISCREPANCIES_OK%"=="True" (
  echo [FAIL] reconciliation discrepancies payload did not expose expected mismatch set
  type "%DISCREPANCIES_FILE%"
  goto :fail
)

echo [7/8] Download reconciliation export...
call :http_request "GET" "%RECON_ROOT%/runs/%RUN_ID%/export?format=csv" "%ADMIN_AUTH_HEADER%" "" "200" "%EXPORT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "from pathlib import Path; payload=Path(r'%EXPORT_FILE%').read_bytes(); ok=(b'run_id,scope,provider,period_start,period_end,status,statement_id' in payload and b'%RUN_ID%' in payload and b'%STATEMENT_ID%' in payload and b'balance_mismatch' in payload and b'unmatched_external' in payload); print(ok)"`) do set "EXPORT_OK=%%t"
if /i not "%EXPORT_OK%"=="True" (
  echo [FAIL] reconciliation export csv is missing expected run/discrepancy content
  goto :fail
)

echo [8/8] Verify persisted rows and audit...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'RUN_STATUS=' ^|^| status::text FROM reconciliation_runs WHERE id = '%RUN_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'RUN_MISMATCHES=' ^|^| COALESCE^(summary-^>^>'mismatches_found', ''^) FROM reconciliation_runs WHERE id = '%RUN_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DISCREPANCY_COUNT=' ^|^| count^(*^)::text FROM reconciliation_discrepancies WHERE run_id = '%RUN_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'BALANCE_KIND_COUNT=' ^|^| count^(*^)::text FROM reconciliation_discrepancies WHERE run_id = '%RUN_ID%' AND discrepancy_type = 'balance_mismatch' AND details-^>^>'kind' IN ^('total_out','closing_balance'^);
>> "%VERIFY_SQL_FILE%" echo SELECT 'UNMATCHED_EXTERNAL_COUNT=' ^|^| count^(*^)::text FROM reconciliation_discrepancies WHERE run_id = '%RUN_ID%' AND discrepancy_type = 'unmatched_external';
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUDIT_UPLOAD=' ^|^| count^(*^)::text FROM audit_log WHERE event_type = 'EXTERNAL_STATEMENT_UPLOADED' AND entity_id = '%STATEMENT_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUDIT_RUN=' ^|^| count^(*^)::text FROM audit_log WHERE event_type = 'RECONCILIATION_RUN_COMPLETED' AND entity_id = '%RUN_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUDIT_EXTERNAL_RUN=' ^|^| count^(*^)::text FROM audit_log WHERE event_type = 'EXTERNAL_RECONCILIATION_COMPLETED' AND entity_id = '%RUN_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] reconciliation verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"RUN_STATUS=completed" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted reconciliation run status is not completed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"RUN_MISMATCHES=3" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted reconciliation summary mismatch count is not 3
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DISCREPANCY_COUNT=3" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted discrepancy count is not 3
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"BALANCE_KIND_COUNT=2" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted balance mismatch count is not 2 for total_out/closing_balance
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"UNMATCHED_EXTERNAL_COUNT=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted unmatched external discrepancy count is not 1
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"AUDIT_UPLOAD=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] external statement audit row missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"AUDIT_RUN=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] reconciliation run audit row missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"AUDIT_EXTERNAL_RUN=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] external reconciliation audit row missing
  type "%VERIFY_LOG%"
  goto :fail
)

echo [SMOKE] Reconciliation run smoke completed.
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
del /q "%STATEMENT_BODY_FILE%" 2>nul
del /q "%STATEMENT_FILE%" 2>nul
del /q "%RUN_BODY_FILE%" 2>nul
del /q "%RUN_FILE%" 2>nul
del /q "%RUN_DETAIL_FILE%" 2>nul
del /q "%DISCREPANCIES_FILE%" 2>nul
del /q "%EXPORT_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\recon_resp_%RANDOM%.json"
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
