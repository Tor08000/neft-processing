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
if "%RESULT_BUCKET%"=="" set "RESULT_BUCKET=neft"
if "%RECON_DATE_FROM%"=="" set "RECON_DATE_FROM=2030-11-01"
if "%RECON_DATE_TO%"=="" set "RECON_DATE_TO=2030-11-30"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"

set "ADMIN_LOGIN_FILE=%TEMP%\recon_admin_login_%RANDOM%.json"
set "ADMIN_LOGIN_BODY=%TEMP%\recon_admin_login_body_%RANDOM%.json"
set "CLIENT_LOGIN_FILE=%TEMP%\recon_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\recon_client_login_body_%RANDOM%.json"
set "ADMIN_VERIFY_FILE=%TEMP%\recon_admin_verify_%RANDOM%.txt"
set "CLIENT_VERIFY_FILE=%TEMP%\recon_client_verify_%RANDOM%.txt"
set "PORTAL_ME_FILE=%TEMP%\recon_portal_me_%RANDOM%.json"
set "CREATE_BODY_FILE=%TEMP%\recon_create_body_%RANDOM%.json"
set "CREATE_FILE=%TEMP%\recon_create_%RANDOM%.json"
set "LIST_FILE=%TEMP%\recon_list_%RANDOM%.json"
set "DETAIL_FILE=%TEMP%\recon_detail_%RANDOM%.json"
set "ATTACH_BODY_FILE=%TEMP%\recon_attach_body_%RANDOM%.json"
set "ATTACH_FILE=%TEMP%\recon_attach_%RANDOM%.json"
set "SENT_FILE=%TEMP%\recon_sent_%RANDOM%.json"
set "ACK_FILE=%TEMP%\recon_ack_%RANDOM%.json"
set "DOC_ACK_FILE=%TEMP%\recon_doc_ack_%RANDOM%.json"
set "DOWNLOAD_FILE=%TEMP%\recon_download_%RANDOM%.pdf"
set "RESULT_FILE=%TEMP%\recon_payload_%RANDOM%.pdf"
set "UPLOAD_LOG=%TEMP%\recon_upload_%RANDOM%.log"
set "VERIFY_SQL_FILE=%TEMP%\recon_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\recon_verify_%RANDOM%.log"
set "CORE_HEALTH_FILE=%TEMP%\recon_core_health_%RANDOM%.json"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "CLIENT_ID="
set "REQUEST_ID="
set "RESULT_HASH="
set "RESULT_OBJECT_KEY="
set "ADMIN_AUTH_HEADER="
set "CLIENT_AUTH_HEADER="

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

echo [3/10] Verify admin and client auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%ADMIN_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%CLIENT_AUTH_HEADER%" "" "204" "%CLIENT_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/portal/me" "%CLIENT_AUTH_HEADER%" "" "200" "%PORTAL_ME_FILE%" || goto :fail

echo [4/10] Create reconciliation request...
python -c "import json; from pathlib import Path; Path(r'%CREATE_BODY_FILE%').write_text(json.dumps({'date_from': r'%RECON_DATE_FROM%','date_to': r'%RECON_DATE_TO%','note':'Created by smoke_reconciliation_request_sign.cmd'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/client/reconciliation-requests" "%CLIENT_AUTH_HEADER%" "%CREATE_BODY_FILE%" "201" "%CREATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CREATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "REQUEST_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CREATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "CREATE_STATUS=%%t"
if "%REQUEST_ID%"=="" (
  echo [FAIL] reconciliation request response missing id
  goto :fail
)
if /i not "%CREATE_STATUS%"=="REQUESTED" (
  echo [FAIL] reconciliation request expected REQUESTED, got %CREATE_STATUS%
  goto :fail
)

echo [5/10] Load request list and detail...
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/reconciliation-requests?limit=10" "%CLIENT_AUTH_HEADER%" "" "200" "%LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ids={str(item.get('id')) for item in payload.get('items') or []}; print('%REQUEST_ID%' in ids)"`) do set "LIST_HAS_ID=%%t"
if /i not "%LIST_HAS_ID%"=="True" (
  echo [FAIL] reconciliation request is missing from client list
  goto :fail
)
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/reconciliation-requests/%REQUEST_ID%" "%CLIENT_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail

echo [6/10] Move request through admin states...
call :http_request "POST" "%CORE_API_BASE%/api/v1/admin/reconciliation-requests/%REQUEST_ID%/mark-in-progress" "%ADMIN_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "IN_PROGRESS_STATUS=%%t"
if /i not "%IN_PROGRESS_STATUS%"=="IN_PROGRESS" (
  echo [FAIL] reconciliation request did not move to IN_PROGRESS
  goto :fail
)

echo [7/10] Upload reconciliation result to MinIO...
for /f "usebackq tokens=*" %%t in (`python -c "from pathlib import Path; import hashlib; payload=b'%%PDF-1.4\\n1 0 obj<< /Type /Catalog >>endobj\\ntrailer<<>>\\n%%%%EOF\\n'; Path(r'%RESULT_FILE%').write_bytes(payload); print(hashlib.sha256(payload).hexdigest())"`) do set "RESULT_HASH=%%t"
if "%RESULT_HASH%"=="" (
  echo [FAIL] failed to generate reconciliation result payload
  goto :fail
)
set "RESULT_OBJECT_KEY=smoke/reconciliation/%REQUEST_ID%.pdf"
docker compose cp "%RESULT_FILE%" core-api:/tmp/reconciliation_smoke_result.pdf > "%UPLOAD_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] failed to copy reconciliation result into core-api container
  type "%UPLOAD_LOG%"
  goto :fail
)
docker compose exec -T core-api python -c "from app.services.s3_storage import S3Storage; s=S3Storage(bucket=r'%RESULT_BUCKET%'); s.ensure_bucket(); s.put_file(r'%RESULT_OBJECT_KEY%', '/tmp/reconciliation_smoke_result.pdf', content_type='application/pdf')" >> "%UPLOAD_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] failed to upload reconciliation result into S3/MinIO
  type "%UPLOAD_LOG%"
  goto :fail
)

echo [8/10] Attach result and mark request sent...
python -c "import json; from pathlib import Path; Path(r'%ATTACH_BODY_FILE%').write_text(json.dumps({'object_key': r'%RESULT_OBJECT_KEY%','bucket': r'%RESULT_BUCKET%','result_hash_sha256': r'%RESULT_HASH%'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/admin/reconciliation-requests/%REQUEST_ID%/attach-result" "%ADMIN_AUTH_HEADER%" "%ATTACH_BODY_FILE%" "200" "%ATTACH_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ATTACH_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "ATTACH_STATUS=%%t"
if /i not "%ATTACH_STATUS%"=="GENERATED" (
  echo [FAIL] attach-result expected GENERATED, got %ATTACH_STATUS%
  goto :fail
)
call :http_request "POST" "%CORE_API_BASE%/api/v1/admin/reconciliation-requests/%REQUEST_ID%/mark-sent" "%ADMIN_AUTH_HEADER%" "" "200" "%SENT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%SENT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "SENT_STATUS=%%t"
if /i not "%SENT_STATUS%"=="SENT" (
  echo [FAIL] reconciliation request expected SENT, got %SENT_STATUS%
  goto :fail
)

echo [9/10] Download and acknowledge result...
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/reconciliation-requests/%REQUEST_ID%/download" "%CLIENT_AUTH_HEADER%" "" "200" "%DOWNLOAD_FILE%" || goto :fail
if not exist "%DOWNLOAD_FILE%" (
  echo [FAIL] reconciliation download file is missing
  goto :fail
)
for %%f in ("%DOWNLOAD_FILE%") do if %%~zf LEQ 0 (
  echo [FAIL] reconciliation download file is empty
  goto :fail
)
call :http_request "POST" "%CORE_API_BASE%/api/v1/client/documents/ACT_RECONCILIATION/%REQUEST_ID%/ack" "%CLIENT_AUTH_HEADER%" "" "201" "%DOC_ACK_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DOC_ACK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('acknowledged') is True)"`) do set "DOC_ACK_OK=%%t"
if /i not "%DOC_ACK_OK%"=="True" (
  echo [FAIL] reconciliation document acknowledgement did not return acknowledged=true
  goto :fail
)
call :http_request "POST" "%CORE_API_BASE%/api/v1/client/reconciliation-requests/%REQUEST_ID%/ack" "%CLIENT_AUTH_HEADER%" "" "200" "%ACK_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ACK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "ACK_STATUS=%%t"
if /i not "%ACK_STATUS%"=="ACKNOWLEDGED" (
  echo [FAIL] reconciliation request acknowledgement expected ACKNOWLEDGED, got %ACK_STATUS%
  goto :fail
)

echo [10/10] Verify persisted reconciliation state...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'REQUEST_STATUS=' ^|^| status::text FROM reconciliation_requests WHERE id = '%REQUEST_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'RESULT_KEY=' ^|^| COALESCE^(result_object_key, ''^) FROM reconciliation_requests WHERE id = '%REQUEST_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'ACK_COUNT=' ^|^| count^(*^)::text FROM document_acknowledgements WHERE client_id = '%CLIENT_ID%' AND document_type = 'ACT_RECONCILIATION' AND document_id = '%REQUEST_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] reconciliation verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"REQUEST_STATUS=ACKNOWLEDGED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] reconciliation request did not persist ACKNOWLEDGED status
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"RESULT_KEY=%RESULT_OBJECT_KEY%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] reconciliation request did not persist result object key
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"ACK_COUNT=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] expected one persisted ACT_RECONCILIATION acknowledgement
  type "%VERIFY_LOG%"
  goto :fail
)

echo [SMOKE] Reconciliation request/sign smoke completed.
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
del /q "%CLIENT_LOGIN_FILE%" 2>nul
del /q "%CLIENT_LOGIN_BODY%" 2>nul
del /q "%ADMIN_VERIFY_FILE%" 2>nul
del /q "%CLIENT_VERIFY_FILE%" 2>nul
del /q "%PORTAL_ME_FILE%" 2>nul
del /q "%CREATE_BODY_FILE%" 2>nul
del /q "%CREATE_FILE%" 2>nul
del /q "%LIST_FILE%" 2>nul
del /q "%DETAIL_FILE%" 2>nul
del /q "%ATTACH_BODY_FILE%" 2>nul
del /q "%ATTACH_FILE%" 2>nul
del /q "%SENT_FILE%" 2>nul
del /q "%ACK_FILE%" 2>nul
del /q "%DOC_ACK_FILE%" 2>nul
del /q "%DOWNLOAD_FILE%" 2>nul
del /q "%RESULT_FILE%" 2>nul
del /q "%UPLOAD_LOG%" 2>nul
del /q "%VERIFY_SQL_FILE%" 2>nul
del /q "%VERIFY_LOG%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
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
