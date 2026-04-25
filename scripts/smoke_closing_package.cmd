@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"
if "%CLOSING_TENANT_ID%"=="" set "CLOSING_TENANT_ID=1"
if "%CLOSING_PERIOD_FROM%"=="" set "CLOSING_PERIOD_FROM=2030-12-01"
if "%CLOSING_PERIOD_TO%"=="" set "CLOSING_PERIOD_TO=2030-12-31"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "LEGACY_ROOT=%CORE_API_BASE%/api/v1"

set "ADMIN_LOGIN_FILE=%TEMP%\closing_admin_login_%RANDOM%.json"
set "ADMIN_LOGIN_BODY=%TEMP%\closing_admin_login_body_%RANDOM%.json"
set "CLIENT_LOGIN_FILE=%TEMP%\closing_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\closing_client_login_body_%RANDOM%.json"
set "ADMIN_VERIFY_FILE=%TEMP%\closing_admin_verify_%RANDOM%.txt"
set "CLIENT_VERIFY_FILE=%TEMP%\closing_client_verify_%RANDOM%.txt"
set "PORTAL_ME_FILE=%TEMP%\closing_portal_me_%RANDOM%.json"
set "GENERATE_BODY_FILE=%TEMP%\closing_generate_body_%RANDOM%.json"
set "GENERATE_FILE=%TEMP%\closing_generate_%RANDOM%.json"
set "DOWNLOAD_PDF_FILE=%TEMP%\closing_doc_pdf_%RANDOM%.bin"
set "DOWNLOAD_XLSX_FILE=%TEMP%\closing_doc_xlsx_%RANDOM%.bin"
set "ACK_FILE=%TEMP%\closing_ack_%RANDOM%.json"
set "FINALIZE_FILE=%TEMP%\closing_finalize_%RANDOM%.json"
set "PACKAGE_ACK_FILE=%TEMP%\closing_package_ack_%RANDOM%.json"
set "PACKAGE_FINALIZE_FILE=%TEMP%\closing_package_finalize_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\closing_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\closing_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\closing_seed_%RANDOM%.log"
set "VERIFY_SQL_FILE=%TEMP%\closing_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\closing_verify_%RANDOM%.log"

set "INVOICE_ID=2fa77f81-a8c7-4c8d-a5ff-20819ed08401"
set "PAYMENT_ID=2fa77f81-a8c7-4c8d-a5ff-20819ed08402"
set "CREDIT_NOTE_ID=2fa77f81-a8c7-4c8d-a5ff-20819ed08403"
set "BILLING_PERIOD_ID=2fa77f81-a8c7-4c8d-a5ff-20819ed08404"
set "ABAC_VERSION_ID=2fa77f81-a8c7-4c8d-a5ff-20819ed08405"
set "ABAC_POLICY_ID=2fa77f81-a8c7-4c8d-a5ff-20819ed08406"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "CLIENT_ID="
set "ADMIN_AUTH_HEADER="
set "CLIENT_AUTH_HEADER="
set "PACKAGE_ID="
set "PACKAGE_VERSION="
set "INVOICE_DOC_ID="
set "ACT_DOC_ID="
set "RECON_DOC_ID="

echo [0/10] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/10] Check auth + core surfaces...
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

echo [1/10] Login admin...
python -c "import json; from pathlib import Path; Path(r'%ADMIN_LOGIN_BODY%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/10] Login client...
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

echo [3/10] Verify auth and client context...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%ADMIN_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%CLIENT_AUTH_HEADER%" "" "204" "%CLIENT_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/portal/me" "%CLIENT_AUTH_HEADER%" "" "200" "%PORTAL_ME_FILE%" || goto :fail

echo [4/10] Seed invoice/payment/refund...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo INSERT INTO billing_periods ^(id, period_type, start_at, end_at, tz, status^) VALUES ^('%BILLING_PERIOD_ID%', 'MONTHLY', TIMESTAMPTZ '%CLOSING_PERIOD_FROM% 00:00:00+00', TIMESTAMPTZ '%CLOSING_PERIOD_TO% 23:59:59+00', 'UTC', 'OPEN'^) ON CONFLICT ON CONSTRAINT uq_billing_period_scope DO UPDATE SET tz = EXCLUDED.tz, status = EXCLUDED.status;
>> "%SEED_SQL_FILE%" echo INSERT INTO invoices ^(id, client_id, number, period_from, period_to, currency, billing_period_id, status, total_amount, tax_amount, total_with_tax, amount_paid, amount_due, amount_refunded, issued_at^) VALUES ^('%INVOICE_ID%', '%CLIENT_ID%', 'INV-CLOSING-SMOKE', DATE '%CLOSING_PERIOD_FROM%', DATE '%CLOSING_PERIOD_TO%', 'RUB', ^(SELECT id FROM billing_periods WHERE period_type = 'MONTHLY' AND start_at = TIMESTAMPTZ '%CLOSING_PERIOD_FROM% 00:00:00+00' AND end_at = TIMESTAMPTZ '%CLOSING_PERIOD_TO% 23:59:59+00'^), 'SENT', 10000, 2000, 12000, 5000, 7000, 0, timezone^('utc', now^(^)^)^) ON CONFLICT ^(id^) DO UPDATE SET client_id = EXCLUDED.client_id, number = EXCLUDED.number, period_from = EXCLUDED.period_from, period_to = EXCLUDED.period_to, currency = EXCLUDED.currency, billing_period_id = EXCLUDED.billing_period_id, status = EXCLUDED.status, total_amount = EXCLUDED.total_amount, tax_amount = EXCLUDED.tax_amount, total_with_tax = EXCLUDED.total_with_tax, amount_paid = EXCLUDED.amount_paid, amount_due = EXCLUDED.amount_due, amount_refunded = EXCLUDED.amount_refunded, issued_at = EXCLUDED.issued_at;
>> "%SEED_SQL_FILE%" echo INSERT INTO invoice_payments ^(id, invoice_id, amount, currency, idempotency_key, status^) VALUES ^('%PAYMENT_ID%', '%INVOICE_ID%', 5000, 'RUB', 'closing-smoke-payment', 'POSTED'^) ON CONFLICT ^(id^) DO NOTHING;
>> "%SEED_SQL_FILE%" echo INSERT INTO credit_notes ^(id, invoice_id, amount, currency, idempotency_key, status^) VALUES ^('%CREDIT_NOTE_ID%', '%INVOICE_ID%', 1000, 'RUB', 'closing-smoke-credit', 'POSTED'^) ON CONFLICT ^(id^) DO NOTHING;
>> "%SEED_SQL_FILE%" echo WITH active_abac_version AS ^(
>> "%SEED_SQL_FILE%" echo   SELECT id
>> "%SEED_SQL_FILE%" echo   FROM abac_policy_versions
>> "%SEED_SQL_FILE%" echo   WHERE status = 'ACTIVE'
>> "%SEED_SQL_FILE%" echo   ORDER BY activated_at DESC NULLS LAST, created_at DESC NULLS LAST
>> "%SEED_SQL_FILE%" echo   LIMIT 1
>> "%SEED_SQL_FILE%" echo ^), ensured_abac_version AS ^(
>> "%SEED_SQL_FILE%" echo   INSERT INTO abac_policy_versions ^(id, name, status, created_at, published_at, activated_at, created_by^)
>> "%SEED_SQL_FILE%" echo   SELECT '%ABAC_VERSION_ID%', 'closing-smoke-default', 'ACTIVE', timezone^('utc', now^(^)^), timezone^('utc', now^(^)^), timezone^('utc', now^(^)^), 'smoke_closing_package'
>> "%SEED_SQL_FILE%" echo   WHERE NOT EXISTS ^(SELECT 1 FROM active_abac_version^)
>> "%SEED_SQL_FILE%" echo   ON CONFLICT ^(id^) DO UPDATE SET status = 'ACTIVE', published_at = EXCLUDED.published_at, activated_at = EXCLUDED.activated_at, created_by = EXCLUDED.created_by
>> "%SEED_SQL_FILE%" echo   RETURNING id
>> "%SEED_SQL_FILE%" echo ^), chosen_abac_version AS ^(
>> "%SEED_SQL_FILE%" echo   SELECT id FROM active_abac_version
>> "%SEED_SQL_FILE%" echo   UNION ALL
>> "%SEED_SQL_FILE%" echo   SELECT id FROM ensured_abac_version
>> "%SEED_SQL_FILE%" echo ^)
>> "%SEED_SQL_FILE%" echo INSERT INTO abac_policies ^(id, version_id, code, effect, priority, actions, resource_type, condition, reason_code, created_at^)
>> "%SEED_SQL_FILE%" echo SELECT '%ABAC_POLICY_ID%', id, 'documents_owner_allow', 'ALLOW', 100, '["documents:download"]'::jsonb, 'DOCUMENT', '{"all":[{"eq":["principal.type","CLIENT"]},{"eq":["resource.owner_client_id","principal.client_id"]}]}'::jsonb, 'DOC_OWNER', timezone^('utc', now^(^)^)
>> "%SEED_SQL_FILE%" echo FROM chosen_abac_version
>> "%SEED_SQL_FILE%" echo LIMIT 1
>> "%SEED_SQL_FILE%" echo ON CONFLICT ON CONSTRAINT uq_abac_policy_version_code DO UPDATE SET effect = EXCLUDED.effect, priority = EXCLUDED.priority, actions = EXCLUDED.actions, resource_type = EXCLUDED.resource_type, condition = EXCLUDED.condition, reason_code = EXCLUDED.reason_code;
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] closing package seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [5/10] Generate closing package...
python -c "import json; from pathlib import Path; Path(r'%GENERATE_BODY_FILE%').write_text(json.dumps({'client_id': r'%CLIENT_ID%','date_from': r'%CLOSING_PERIOD_FROM%','date_to': r'%CLOSING_PERIOD_TO%','version_mode':'AUTO','force_new_version': True,'tenant_id': int(r'%CLOSING_TENANT_ID%')}), encoding='utf-8')"
call :http_request "POST" "%LEGACY_ROOT%/admin/closing-packages/generate" "%ADMIN_AUTH_HEADER%" "%GENERATE_BODY_FILE%" "200" "%GENERATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%GENERATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('package_id',''))"`) do set "PACKAGE_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%GENERATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('version',''))"`) do set "PACKAGE_VERSION=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%GENERATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); docs={str(item.get('type')): str(item.get('id')) for item in data.get('documents') or []}; print(docs.get('INVOICE',''))"`) do set "INVOICE_DOC_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%GENERATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); docs={str(item.get('type')): str(item.get('id')) for item in data.get('documents') or []}; print(docs.get('ACT',''))"`) do set "ACT_DOC_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%GENERATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); docs={str(item.get('type')): str(item.get('id')) for item in data.get('documents') or []}; print(docs.get('RECONCILIATION_ACT',''))"`) do set "RECON_DOC_ID=%%t"
if "%PACKAGE_ID%"=="" (
  echo [FAIL] generate response missing package_id
  goto :fail
)
if "%INVOICE_DOC_ID%"=="" (
  echo [FAIL] generate response missing invoice document id
  goto :fail
)
if "%ACT_DOC_ID%"=="" (
  echo [FAIL] generate response missing act document id
  goto :fail
)
if "%RECON_DOC_ID%"=="" (
  echo [FAIL] generate response missing reconciliation document id
  goto :fail
)

echo [6/10] Download generated document files...
call :download_pair "%INVOICE_DOC_ID%" || goto :fail
call :download_pair "%ACT_DOC_ID%" || goto :fail
call :download_pair "%RECON_DOC_ID%" || goto :fail

echo [7/10] Acknowledge generated documents...
call :ack_document "%INVOICE_DOC_ID%" || goto :fail
call :ack_document "%ACT_DOC_ID%" || goto :fail
call :ack_document "%RECON_DOC_ID%" || goto :fail

echo [8/10] Finalize generated documents...
call :finalize_document "%INVOICE_DOC_ID%" || goto :fail
call :finalize_document "%ACT_DOC_ID%" || goto :fail
call :finalize_document "%RECON_DOC_ID%" || goto :fail

echo [9/10] Acknowledge and finalize closing package...
call :http_request "POST" "%LEGACY_ROOT%/client/closing-packages/%PACKAGE_ID%/ack" "%CLIENT_AUTH_HEADER%" "" "200" "%PACKAGE_ACK_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PACKAGE_ACK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('acknowledged') is True)"`) do set "PACKAGE_ACK_OK=%%t"
if /i not "%PACKAGE_ACK_OK%"=="True" (
  echo [FAIL] package acknowledgement response is not acknowledged=true
  goto :fail
)
call :http_request "POST" "%LEGACY_ROOT%/admin/closing-packages/%PACKAGE_ID%/finalize" "%ADMIN_AUTH_HEADER%" "" "200" "%PACKAGE_FINALIZE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PACKAGE_FINALIZE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "PACKAGE_STATUS=%%t"
if /i not "%PACKAGE_STATUS%"=="FINALIZED" (
  echo [FAIL] package finalize response expected FINALIZED, got %PACKAGE_STATUS%
  goto :fail
)

echo [10/10] Verify persisted final states...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'PACKAGE_STATUS=' ^|^| status::text FROM closing_packages WHERE id = '%PACKAGE_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'DOC_STATUS=' ^|^| document_type::text ^|^| '=' ^|^| status::text FROM documents WHERE id IN ^('%INVOICE_DOC_ID%', '%ACT_DOC_ID%', '%RECON_DOC_ID%'^) ORDER BY document_type::text;
>> "%VERIFY_SQL_FILE%" echo SELECT 'ACK_COUNT=' ^|^| count^(*^)::text FROM document_acknowledgements WHERE client_id = '%CLIENT_ID%' AND document_id IN ^('%INVOICE_DOC_ID%', '%ACT_DOC_ID%', '%RECON_DOC_ID%'^);
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] closing package verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"PACKAGE_STATUS=FINALIZED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted closing package status is not FINALIZED
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DOC_STATUS=ACT=FINALIZED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] ACT document was not finalized
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DOC_STATUS=INVOICE=FINALIZED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] INVOICE document was not finalized
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"DOC_STATUS=RECONCILIATION_ACT=FINALIZED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] RECONCILIATION_ACT document was not finalized
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"ACK_COUNT=3" "%VERIFY_LOG%" >nul || (
  echo [FAIL] expected 3 persisted document acknowledgements
  type "%VERIFY_LOG%"
  goto :fail
)

echo [SMOKE] Closing package smoke completed.
call :cleanup
exit /b 0

:download_pair
set "DOCUMENT_ID=%~1"
call :http_request "GET" "%LEGACY_ROOT%/client/documents/%DOCUMENT_ID%/download?file_type=PDF" "%CLIENT_AUTH_HEADER%" "" "200" "%DOWNLOAD_PDF_FILE%" || exit /b 1
call :http_request "GET" "%LEGACY_ROOT%/client/documents/%DOCUMENT_ID%/download?file_type=XLSX" "%CLIENT_AUTH_HEADER%" "" "200" "%DOWNLOAD_XLSX_FILE%" || exit /b 1
for %%f in ("%DOWNLOAD_PDF_FILE%" "%DOWNLOAD_XLSX_FILE%") do (
  if not exist "%%~f" exit /b 1
  if %%~zf LEQ 0 exit /b 1
)
exit /b 0

:ack_document
set "DOCUMENT_ID=%~1"
call :http_request "POST" "%LEGACY_ROOT%/client/documents/%DOCUMENT_ID%/ack" "%CLIENT_AUTH_HEADER%" "" "201" "%ACK_FILE%" || exit /b 1
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ACK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('acknowledged') is True and str(data.get('document_type') or '') != '')"`) do set "DOC_ACK_OK=%%t"
if /i not "%DOC_ACK_OK%"=="True" exit /b 1
exit /b 0

:finalize_document
set "DOCUMENT_ID=%~1"
call :http_request "POST" "%LEGACY_ROOT%/admin/documents/%DOCUMENT_ID%/finalize" "%ADMIN_AUTH_HEADER%" "" "200" "%FINALIZE_FILE%" || exit /b 1
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%FINALIZE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "DOC_STATUS=%%t"
if /i not "%DOC_STATUS%"=="FINALIZED" exit /b 1
exit /b 0

:fail
call :cleanup
echo [SMOKE] Failed.
exit /b 1

:resolve_auth_openapi
set "AUTH_CODE="
set "AUTH_OPENAPI_URL="
for %%u in ("%AUTH_URL%/openapi.json" "%AUTH_HOST_BASE%/openapi.json" "%AUTH_HOST_BASE%/api/auth/openapi.json") do (
  for /f "usebackq tokens=*" %%c in (`curl -s -S -o NUL -w "%%{http_code}" %%~u 2^>nul`) do (
    if "%%c"=="200" (
      set "AUTH_CODE=%%c"
      set "AUTH_OPENAPI_URL=%%~u"
      exit /b 0
    )
  )
)
exit /b 0

:cleanup
del /q "%ADMIN_LOGIN_FILE%" 2>nul
del /q "%ADMIN_LOGIN_BODY%" 2>nul
del /q "%CLIENT_LOGIN_FILE%" 2>nul
del /q "%CLIENT_LOGIN_BODY%" 2>nul
del /q "%ADMIN_VERIFY_FILE%" 2>nul
del /q "%CLIENT_VERIFY_FILE%" 2>nul
del /q "%PORTAL_ME_FILE%" 2>nul
del /q "%GENERATE_BODY_FILE%" 2>nul
del /q "%GENERATE_FILE%" 2>nul
del /q "%DOWNLOAD_PDF_FILE%" 2>nul
del /q "%DOWNLOAD_XLSX_FILE%" 2>nul
del /q "%ACK_FILE%" 2>nul
del /q "%FINALIZE_FILE%" 2>nul
del /q "%PACKAGE_ACK_FILE%" 2>nul
del /q "%PACKAGE_FINALIZE_FILE%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\closing_package_resp_%RANDOM%.json"
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
