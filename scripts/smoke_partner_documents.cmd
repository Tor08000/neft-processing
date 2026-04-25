@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "PARTNER_EDO_URL=%CORE_ROOT%/partner/api/v1/edo"

set "LOGIN_FILE=%TEMP%\partner_documents_login_%RANDOM%.json"
set "LOGIN_BODY_FILE=%TEMP%\partner_documents_login_body_%RANDOM%.json"
set "PORTAL_ME_FILE=%TEMP%\partner_documents_me_%RANDOM%.json"
set "LIST_FILE=%TEMP%\partner_documents_list_%RANDOM%.json"
set "DETAIL_FILE=%TEMP%\partner_documents_detail_%RANDOM%.json"
set "ARTIFACTS_FILE=%TEMP%\partner_documents_artifacts_%RANDOM%.json"
set "TRANSITIONS_FILE=%TEMP%\partner_documents_transitions_%RANDOM%.json"
set "ACK_FILE=%TEMP%\partner_documents_ack_%RANDOM%.json"
set "VERIFY_FILE=%TEMP%\partner_documents_verify_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\partner_documents_core_health_%RANDOM%.json"
set "SQL_FILE=%TEMP%\partner_documents_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\partner_documents_seed_%RANDOM%.log"

set "ACCOUNT_ID=6f2fd8a4-0a19-4fbe-8ed7-1fb30d3ac001"
set "COUNTERPARTY_ID=6f2fd8a4-0a19-4fbe-8ed7-1fb30d3ac002"
set "DOCUMENT_ID=6f2fd8a4-0a19-4fbe-8ed7-1fb30d3ac003"
set "REGISTRY_ID=6f2fd8a4-0a19-4fbe-8ed7-1fb30d3ac004"
set "ARTIFACT_ID=6f2fd8a4-0a19-4fbe-8ed7-1fb30d3ac005"
set "TRANSITION_ID=6f2fd8a4-0a19-4fbe-8ed7-1fb30d3ac006"
set "PARTNER_TOKEN="
set "PARTNER_ID="
set "PARTNER_AUTH_HEADER="

echo [0/8] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/8] Check gateway auth surface...
set "AUTH_CODE="
call :resolve_auth_openapi || goto :fail
if "%AUTH_CODE%"=="" (
  echo [FAIL] auth gateway is not reachable at %AUTH_URL%
  goto :fail
)
if not "%AUTH_CODE%"=="200" (
  echo [FAIL] auth gateway expected 200 from a mounted OpenAPI route near %AUTH_URL%, got %AUTH_CODE%
  goto :fail
)
call :wait_for_status "%CORE_API_BASE%/health" "200" 20 2 || goto :fail
call :http_request "GET" "%CORE_API_BASE%/health" "" "" "200" "%CORE_HEALTH_FILE%" || goto :fail

echo [1/8] Login partner...
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','password': r'%PARTNER_PASSWORD%','portal':'partner'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%t"
if "%PARTNER_TOKEN%"=="" (
  echo [FAIL] partner login missing access_token
  goto :fail
)
set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

echo [2/8] Verify partner auth...
call :http_request "GET" "%CORE_ROOT%/partner/auth/verify" "%PARTNER_AUTH_HEADER%" "" "204" "%VERIFY_FILE%" || goto :fail

echo [3/8] Resolve partner context...
call :http_request "GET" "%CORE_ROOT%/portal/me" "%PARTNER_AUTH_HEADER%" "" "200" "%PORTAL_ME_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_ME_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); partner=data.get('partner') or {}; org=data.get('org') or {}; print(partner.get('partner_id') or org.get('id') or '')"`) do set "PARTNER_ID=%%t"
if "%PARTNER_ID%"=="" (
  echo [FAIL] partner portal/me did not return partner context
  goto :fail
)

echo [4/8] Seed partner EDO document...
> "%SQL_FILE%" echo SET search_path TO processing_core;
>> "%SQL_FILE%" echo INSERT INTO edo_accounts ^(id, provider, name, org_inn, box_id, credentials_ref, webhook_secret_ref, is_active^) VALUES ^('%ACCOUNT_ID%', 'SBIS', 'Partner Smoke Account', '7701234567', 'smoke-box', 'smoke-creds', 'smoke-secret', true^) ON CONFLICT ^(id^) DO UPDATE SET name = EXCLUDED.name, org_inn = EXCLUDED.org_inn, box_id = EXCLUDED.box_id, credentials_ref = EXCLUDED.credentials_ref, webhook_secret_ref = EXCLUDED.webhook_secret_ref, is_active = EXCLUDED.is_active;
>> "%SQL_FILE%" echo INSERT INTO edo_counterparties ^(id, subject_type, subject_id, provider, provider_counterparty_id, provider_box_id, display_name, meta^) VALUES ^('%COUNTERPARTY_ID%', 'PARTNER', '%PARTNER_ID%', 'SBIS', 'smoke-counterparty', 'smoke-counterparty-box', 'Smoke Counterparty', jsonb_build_object^('source', 'smoke'^)^) ON CONFLICT ^(id^) DO UPDATE SET subject_type = EXCLUDED.subject_type, subject_id = EXCLUDED.subject_id, provider = EXCLUDED.provider, provider_counterparty_id = EXCLUDED.provider_counterparty_id, provider_box_id = EXCLUDED.provider_box_id, display_name = EXCLUDED.display_name, meta = EXCLUDED.meta;
>> "%SQL_FILE%" echo INSERT INTO edo_documents ^(id, provider, account_id, subject_type, subject_id, document_registry_id, document_kind, provider_doc_id, provider_thread_id, status, counterparty_id, send_dedupe_key, attempts_send, attempts_status, next_retry_at, last_error, last_status_payload, requires_manual_intervention^) VALUES ^('%DOCUMENT_ID%', 'SBIS', '%ACCOUNT_ID%', 'PARTNER', '%PARTNER_ID%', '%REGISTRY_ID%', 'ACT', 'smoke-provider-doc', 'smoke-thread-doc', 'DELIVERED', '%COUNTERPARTY_ID%', 'partner-documents-smoke', 1, 1, NULL, NULL, jsonb_build_object^('source', 'smoke', 'status', 'DELIVERED'^), false^) ON CONFLICT ^(id^) DO UPDATE SET provider = EXCLUDED.provider, account_id = EXCLUDED.account_id, subject_type = EXCLUDED.subject_type, subject_id = EXCLUDED.subject_id, document_registry_id = EXCLUDED.document_registry_id, document_kind = EXCLUDED.document_kind, provider_doc_id = EXCLUDED.provider_doc_id, provider_thread_id = EXCLUDED.provider_thread_id, status = EXCLUDED.status, counterparty_id = EXCLUDED.counterparty_id, send_dedupe_key = EXCLUDED.send_dedupe_key, attempts_send = EXCLUDED.attempts_send, attempts_status = EXCLUDED.attempts_status, next_retry_at = EXCLUDED.next_retry_at, last_error = EXCLUDED.last_error, last_status_payload = EXCLUDED.last_status_payload, requires_manual_intervention = EXCLUDED.requires_manual_intervention;
>> "%SQL_FILE%" echo INSERT INTO edo_artifacts ^(id, edo_document_id, artifact_type, document_registry_id, content_hash, provider_ref^) VALUES ^('%ARTIFACT_ID%', '%DOCUMENT_ID%', 'SIGNED_PACKAGE', '%REGISTRY_ID%', 'smoke-artifact-hash', jsonb_build_object^('object_key', 'partner-documents/smoke-act.pdf'^)^) ON CONFLICT ^(id^) DO UPDATE SET edo_document_id = EXCLUDED.edo_document_id, artifact_type = EXCLUDED.artifact_type, document_registry_id = EXCLUDED.document_registry_id, content_hash = EXCLUDED.content_hash, provider_ref = EXCLUDED.provider_ref;
>> "%SQL_FILE%" echo INSERT INTO edo_transitions ^(id, edo_document_id, from_status, to_status, reason_code, payload, actor_type, actor_id^) VALUES ^('%TRANSITION_ID%', '%DOCUMENT_ID%', 'SENT', 'DELIVERED', 'smoke_delivery', jsonb_build_object^('source', 'smoke'^), 'SYSTEM', 'smoke-partner-documents'^) ON CONFLICT ^(id^) DO UPDATE SET edo_document_id = EXCLUDED.edo_document_id, from_status = EXCLUDED.from_status, to_status = EXCLUDED.to_status, reason_code = EXCLUDED.reason_code, payload = EXCLUDED.payload, actor_type = EXCLUDED.actor_type, actor_id = EXCLUDED.actor_id;
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] partner documents seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [5/8] List partner EDO documents...
call :http_request "GET" "%PARTNER_EDO_URL%/documents" "%PARTNER_AUTH_HEADER%" "" "200" "%LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; items=json.loads(Path(r'%LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '[]'); print(sum(1 for item in items if item.get('id') == r'%DOCUMENT_ID%'))"`) do set "DOC_MATCHES=%%t"
if not "%DOC_MATCHES%"=="1" (
  echo [FAIL] seeded partner document not found in list
  goto :fail
)

echo [6/8] Fetch document details...
call :http_request "GET" "%PARTNER_EDO_URL%/documents/%DOCUMENT_ID%" "%PARTNER_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print((data.get('id') == r'%DOCUMENT_ID%') and (str(data.get('status') or '').upper() == 'DELIVERED'))"`) do set "DETAIL_OK=%%t"
if /i not "%DETAIL_OK%"=="True" (
  echo [FAIL] document details did not match seeded DELIVERED document
  goto :fail
)

echo [7/8] Fetch artifacts and transitions...
call :http_request "GET" "%PARTNER_EDO_URL%/documents/%DOCUMENT_ID%/artifacts" "%PARTNER_AUTH_HEADER%" "" "200" "%ARTIFACTS_FILE%" || goto :fail
call :http_request "GET" "%PARTNER_EDO_URL%/documents/%DOCUMENT_ID%/transitions" "%PARTNER_AUTH_HEADER%" "" "200" "%TRANSITIONS_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; artifacts=json.loads(Path(r'%ARTIFACTS_FILE%').read_text(encoding='utf-8', errors='ignore') or '[]'); transitions=json.loads(Path(r'%TRANSITIONS_FILE%').read_text(encoding='utf-8', errors='ignore') or '[]'); ok=any(item.get('id') == r'%ARTIFACT_ID%' for item in artifacts) and any(item.get('id') == r'%TRANSITION_ID%' for item in transitions); print(ok)"`) do set "CHILDREN_OK=%%t"
if /i not "%CHILDREN_OK%"=="True" (
  echo [FAIL] artifacts or transitions did not include seeded rows
  goto :fail
)

echo [8/8] Acknowledge document...
call :http_request "POST" "%PARTNER_EDO_URL%/documents/%DOCUMENT_ID%/ack" "%PARTNER_AUTH_HEADER%" "" "200" "%ACK_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ACK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('acknowledged') is True and data.get('document_id') == r'%DOCUMENT_ID%')"`) do set "ACK_OK=%%t"
if /i not "%ACK_OK%"=="True" (
  echo [FAIL] acknowledge response did not match seeded document
  goto :fail
)

echo [SMOKE] Partner documents smoke completed.
call :cleanup
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
del /q "%LOGIN_FILE%" 2>nul
del /q "%LOGIN_BODY_FILE%" 2>nul
del /q "%PORTAL_ME_FILE%" 2>nul
del /q "%LIST_FILE%" 2>nul
del /q "%DETAIL_FILE%" 2>nul
del /q "%ARTIFACTS_FILE%" 2>nul
del /q "%TRANSITIONS_FILE%" 2>nul
del /q "%ACK_FILE%" 2>nul
del /q "%VERIFY_FILE%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
del /q "%SQL_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\partner_documents_resp_%RANDOM%.json"
if "%BODY_FILE%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
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
