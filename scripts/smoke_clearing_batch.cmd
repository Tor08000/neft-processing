@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"
if "%CLEARING_DATE%"=="" set "CLEARING_DATE=2099-12-01"
if "%MERCHANT_ONE%"=="" set "MERCHANT_ONE=smoke-clearing-m1"
if "%MERCHANT_TWO%"=="" set "MERCHANT_TWO=smoke-clearing-m2"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"

set "ADMIN_LOGIN_FILE=%TEMP%\clearing_admin_login_%RANDOM%.json"
set "ADMIN_LOGIN_BODY=%TEMP%\clearing_admin_login_body_%RANDOM%.json"
set "ADMIN_VERIFY_FILE=%TEMP%\clearing_admin_verify_%RANDOM%.txt"
set "CORE_HEALTH_FILE=%TEMP%\clearing_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\clearing_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\clearing_seed_%RANDOM%.log"
set "RUN_FILE=%TEMP%\clearing_run_%RANDOM%.json"
set "RUN_REPEAT_FILE=%TEMP%\clearing_run_repeat_%RANDOM%.json"
set "VERIFY_SQL_FILE=%TEMP%\clearing_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\clearing_verify_%RANDOM%.log"

set "ADMIN_TOKEN="
set "ADMIN_AUTH_HEADER="

echo [0/6] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/6] Check auth + core surfaces...
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

echo [1/6] Login admin...
python -c "import json; from pathlib import Path; Path(r'%ADMIN_LOGIN_BODY%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/6] Verify admin auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%ADMIN_VERIFY_FILE%" || goto :fail

echo [3/6] Seed finalized billing summaries for clearing...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo DELETE FROM billing_job_runs WHERE job_type = 'CLEARING' AND jsonb_extract_path_text^(params::jsonb, 'clearing_date'^) = '%CLEARING_DATE%';
>> "%SEED_SQL_FILE%" echo DELETE FROM clearing WHERE batch_date = '%CLEARING_DATE%' AND merchant_id IN ^('%MERCHANT_ONE%', '%MERCHANT_TWO%'^);
>> "%SEED_SQL_FILE%" echo DELETE FROM billing_summary WHERE billing_date = '%CLEARING_DATE%' AND merchant_id IN ^('%MERCHANT_ONE%', '%MERCHANT_TWO%'^);
>> "%SEED_SQL_FILE%" echo INSERT INTO billing_summary ^(id, billing_date, client_id, merchant_id, product_type, currency, total_amount, operations_count, commission_amount, status, finalized_at^)
>> "%SEED_SQL_FILE%" echo VALUES
>> "%SEED_SQL_FILE%" echo   ^('smoke-clearing-summary-1', '%CLEARING_DATE%', 'smoke-client-1', '%MERCHANT_ONE%', 'AI92', 'RUB', 500, 2, 0, 'FINALIZED', timezone^('utc', now^(^)^)^),
>> "%SEED_SQL_FILE%" echo   ^('smoke-clearing-summary-2', '%CLEARING_DATE%', 'smoke-client-2', '%MERCHANT_ONE%', 'AI95', 'RUB', 700, 1, 0, 'FINALIZED', timezone^('utc', now^(^)^)^),
>> "%SEED_SQL_FILE%" echo   ^('smoke-clearing-summary-3', '%CLEARING_DATE%', 'smoke-client-3', '%MERCHANT_TWO%', 'AI95', 'USD', 900, 1, 0, 'FINALIZED', timezone^('utc', now^(^)^)^)
>> "%SEED_SQL_FILE%" echo ON CONFLICT ON CONSTRAINT uq_billing_summary_unique_scope DO UPDATE SET
>> "%SEED_SQL_FILE%" echo   total_amount = EXCLUDED.total_amount,
>> "%SEED_SQL_FILE%" echo   operations_count = EXCLUDED.operations_count,
>> "%SEED_SQL_FILE%" echo   commission_amount = EXCLUDED.commission_amount,
>> "%SEED_SQL_FILE%" echo   status = EXCLUDED.status,
>> "%SEED_SQL_FILE%" echo   finalized_at = EXCLUDED.finalized_at;
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] clearing seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/6] Run clearing...
call :http_request "POST" "%CORE_API_BASE%/api/v1/admin/clearing/run?clearing_date=%CLEARING_DATE%" "%ADMIN_AUTH_HEADER%" "" "200" "%RUN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%RUN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=payload == {'clearing_date': r'%CLEARING_DATE%', 'created': 2}; print(ok)"`) do set "RUN_OK=%%t"
if /i not "%RUN_OK%"=="True" (
  echo [FAIL] clearing run response did not match the live clearing owner contract
  type "%RUN_FILE%"
  goto :fail
)

echo [5/6] Re-run clearing and verify idempotent result...
call :http_request "POST" "%CORE_API_BASE%/api/v1/admin/clearing/run?clearing_date=%CLEARING_DATE%" "%ADMIN_AUTH_HEADER%" "" "200" "%RUN_REPEAT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%RUN_REPEAT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=payload == {'clearing_date': r'%CLEARING_DATE%', 'created': 0, 'reason': 'already_exists'}; print(ok)"`) do set "IDEMPOTENT_OK=%%t"
if /i not "%IDEMPOTENT_OK%"=="True" (
  echo [FAIL] repeated clearing run did not expose the expected already_exists response
  type "%RUN_REPEAT_FILE%"
  goto :fail
)

echo [6/6] Verify persisted clearing rows and job run...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'BATCH_COUNT=' ^|^| count^(*^)::text FROM clearing WHERE batch_date = '%CLEARING_DATE%' AND merchant_id IN ^('%MERCHANT_ONE%', '%MERCHANT_TWO%'^);
>> "%VERIFY_SQL_FILE%" echo SELECT 'MERCHANT_ONE_TOTAL=' ^|^| total_amount::text FROM clearing WHERE batch_date = '%CLEARING_DATE%' AND merchant_id = '%MERCHANT_ONE%' AND currency = 'RUB';
>> "%VERIFY_SQL_FILE%" echo SELECT 'MERCHANT_ONE_DETAILS=' ^|^| json_array_length^(details^)::text FROM clearing WHERE batch_date = '%CLEARING_DATE%' AND merchant_id = '%MERCHANT_ONE%' AND currency = 'RUB';
>> "%VERIFY_SQL_FILE%" echo SELECT 'MERCHANT_TWO_TOTAL=' ^|^| total_amount::text FROM clearing WHERE batch_date = '%CLEARING_DATE%' AND merchant_id = '%MERCHANT_TWO%' AND currency = 'USD';
>> "%VERIFY_SQL_FILE%" echo SELECT 'JOB_RUN_COUNT=' ^|^| count^(*^)::text FROM billing_job_runs WHERE job_type = 'CLEARING' AND jsonb_extract_path_text^(params::jsonb, 'clearing_date'^) = '%CLEARING_DATE%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'JOB_RUN_SUCCESS_COUNT=' ^|^| count^(*^)::text FROM billing_job_runs WHERE job_type = 'CLEARING' AND jsonb_extract_path_text^(params::jsonb, 'clearing_date'^) = '%CLEARING_DATE%' AND status = 'SUCCESS';
>> "%VERIFY_SQL_FILE%" echo SELECT 'JOB_RUN_CREATED_TWO=' ^|^| count^(*^)::text FROM billing_job_runs WHERE job_type = 'CLEARING' AND jsonb_extract_path_text^(params::jsonb, 'clearing_date'^) = '%CLEARING_DATE%' AND jsonb_extract_path_text^(metrics::jsonb, 'created'^) = '2';
>> "%VERIFY_SQL_FILE%" echo SELECT 'JOB_RUN_ALREADY_EXISTS=' ^|^| count^(*^)::text FROM billing_job_runs WHERE job_type = 'CLEARING' AND jsonb_extract_path_text^(params::jsonb, 'clearing_date'^) = '%CLEARING_DATE%' AND jsonb_extract_path_text^(metrics::jsonb, 'reason'^) = 'already_exists';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] clearing verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"BATCH_COUNT=2" "%VERIFY_LOG%" >nul || (
  echo [FAIL] expected two persisted clearing rows for the smoke date
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"MERCHANT_ONE_TOTAL=1200" "%VERIFY_LOG%" >nul || (
  echo [FAIL] merchant one clearing total is not 1200
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"MERCHANT_ONE_DETAILS=2" "%VERIFY_LOG%" >nul || (
  echo [FAIL] merchant one clearing detail count is not 2
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"MERCHANT_TWO_TOTAL=900" "%VERIFY_LOG%" >nul || (
  echo [FAIL] merchant two clearing total is not 900
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"JOB_RUN_COUNT=2" "%VERIFY_LOG%" >nul || (
  echo [FAIL] expected two CLEARING job rows for the smoke date after run plus already_exists replay
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"JOB_RUN_SUCCESS_COUNT=2" "%VERIFY_LOG%" >nul || (
  echo [FAIL] expected two successful CLEARING job rows for the smoke date
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"JOB_RUN_CREATED_TWO=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] CLEARING job history is missing the initial created=2 row
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"JOB_RUN_ALREADY_EXISTS=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] CLEARING job history is missing the already_exists replay row
  type "%VERIFY_LOG%"
  goto :fail
)

echo [SMOKE] Clearing batch smoke completed.
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
del /q "%ADMIN_LOGIN_FILE%" 2>nul
del /q "%ADMIN_LOGIN_BODY%" 2>nul
del /q "%ADMIN_VERIFY_FILE%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
del /q "%SEED_SQL_FILE%" 2>nul
del /q "%SEED_LOG%" 2>nul
del /q "%RUN_FILE%" 2>nul
del /q "%RUN_REPEAT_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\clearing_resp_%RANDOM%.json"
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
