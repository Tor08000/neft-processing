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

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "REQUEST_TITLE=Smoke support request"
set "REQUEST_DESCRIPTION=Created by smoke_support_ticket.cmd"

set "ADMIN_LOGIN_FILE=%TEMP%\support_admin_login_%RANDOM%.json"
set "ADMIN_LOGIN_BODY=%TEMP%\support_admin_login_body_%RANDOM%.json"
set "CLIENT_LOGIN_FILE=%TEMP%\support_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\support_client_login_body_%RANDOM%.json"
set "ADMIN_VERIFY_FILE=%TEMP%\support_admin_verify_%RANDOM%.txt"
set "CLIENT_VERIFY_FILE=%TEMP%\support_client_verify_%RANDOM%.txt"
set "CREATE_BODY_FILE=%TEMP%\support_create_body_%RANDOM%.json"
set "CREATE_FILE=%TEMP%\support_create_%RANDOM%.json"
set "LIST_FILE=%TEMP%\support_list_%RANDOM%.json"
set "DETAIL_FILE=%TEMP%\support_detail_%RANDOM%.json"
set "UPDATE_BODY_FILE=%TEMP%\support_update_body_%RANDOM%.json"
set "UPDATE_FILE=%TEMP%\support_update_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\support_core_health_%RANDOM%.json"
set "VERIFY_SQL_FILE=%TEMP%\support_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\support_verify_%RANDOM%.log"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "REQUEST_ID="
set "ADMIN_AUTH_HEADER="
set "CLIENT_AUTH_HEADER="

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
python -c "import json; from pathlib import Path; Path(r'%ADMIN_LOGIN_BODY%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/8] Login client...
python -c "import json; from pathlib import Path; Path(r'%CLIENT_LOGIN_BODY%').write_text(json.dumps({'email': r'%CLIENT_EMAIL%','password': r'%CLIENT_PASSWORD%','portal':'client'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%CLIENT_LOGIN_BODY%" "200" "%CLIENT_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CLIENT_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%t"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] client login missing access_token
  goto :fail
)
set "CLIENT_AUTH_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
if /i "%CLIENT_TOKEN:~0,7%"=="Bearer " set "CLIENT_AUTH_HEADER=Authorization: %CLIENT_TOKEN%"

echo [3/8] Verify admin and client auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%ADMIN_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%CLIENT_AUTH_HEADER%" "" "204" "%CLIENT_VERIFY_FILE%" || goto :fail

echo [4/8] Create support request via compatibility route...
python -c "import json; from pathlib import Path; Path(r'%CREATE_BODY_FILE%').write_text(json.dumps({'scope_type':'CLIENT','subject_type':'OTHER','title':r'%REQUEST_TITLE%','description':r'%REQUEST_DESCRIPTION%','correlation_id':'smoke-support','event_id':'smoke-support-event'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/support/requests" "%CLIENT_AUTH_HEADER%" "%CREATE_BODY_FILE%" "201" "%CREATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CREATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "REQUEST_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%CREATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "CREATE_STATUS=%%t"
if "%REQUEST_ID%"=="" (
  echo [FAIL] support request response missing id
  goto :fail
)
if /i not "%CREATE_STATUS%"=="OPEN" (
  echo [FAIL] support request create expected OPEN, got %CREATE_STATUS%
  goto :fail
)

echo [5/8] List and inspect support request...
call :http_request "GET" "%CORE_API_BASE%/api/v1/support/requests?limit=10" "%CLIENT_AUTH_HEADER%" "" "200" "%LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ids={str(item.get('id')) for item in payload.get('items') or []}; print('%REQUEST_ID%' in ids)"`) do set "LIST_HAS_ID=%%t"
if /i not "%LIST_HAS_ID%"=="True" (
  echo [FAIL] created support request is missing from client list
  goto :fail
)
call :http_request "GET" "%CORE_API_BASE%/api/v1/support/requests/%REQUEST_ID%" "%CLIENT_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=str(data.get('id') or '') == r'%REQUEST_ID%' and str(data.get('status') or '').upper() == 'OPEN'; print(ok)"`) do set "DETAIL_OPEN_OK=%%t"
if /i not "%DETAIL_OPEN_OK%"=="True" (
  echo [FAIL] support request detail is missing expected OPEN state
  goto :fail
)

echo [6/8] Resolve support request as admin...
python -c "import json; from pathlib import Path; Path(r'%UPDATE_BODY_FILE%').write_text(json.dumps({'status':'RESOLVED'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/support/requests/%REQUEST_ID%/status" "%ADMIN_AUTH_HEADER%" "%UPDATE_BODY_FILE%" "200" "%UPDATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%UPDATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "UPDATE_STATUS=%%t"
if /i not "%UPDATE_STATUS%"=="RESOLVED" (
  echo [FAIL] support request status update expected RESOLVED, got %UPDATE_STATUS%
  goto :fail
)
call :http_request "GET" "%CORE_API_BASE%/api/v1/support/requests/%REQUEST_ID%" "%CLIENT_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "DETAIL_STATUS=%%t"
if /i not "%DETAIL_STATUS%"=="RESOLVED" (
  echo [FAIL] client detail did not reflect RESOLVED state, got %DETAIL_STATUS%
  goto :fail
)

echo [7/8] Verify canonical cases owner row...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CASE_STATUS=' ^|^| status::text FROM cases WHERE id = '%REQUEST_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CASE_QUEUE=' ^|^| queue::text FROM cases WHERE id = '%REQUEST_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CASE_SOURCE=' ^|^| COALESCE^(case_source_ref_type, ''^) FROM cases WHERE id = '%REQUEST_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CASE_EVENTS=' ^|^| count^(*^)::text FROM case_events WHERE case_id = '%REQUEST_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] support case verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CASE_STATUS=RESOLVED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] canonical case did not reach RESOLVED
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CASE_QUEUE=SUPPORT" "%VERIFY_LOG%" >nul || (
  echo [FAIL] canonical case queue is not SUPPORT
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CASE_SOURCE=SUPPORT_REQUEST" "%VERIFY_LOG%" >nul || (
  echo [FAIL] canonical case is not marked as support_requests compatibility source
  type "%VERIFY_LOG%"
  goto :fail
)

echo [8/8] Support ticket smoke completed.
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
del /q "%CREATE_BODY_FILE%" 2>nul
del /q "%CREATE_FILE%" 2>nul
del /q "%LIST_FILE%" 2>nul
del /q "%DETAIL_FILE%" 2>nul
del /q "%UPDATE_BODY_FILE%" 2>nul
del /q "%UPDATE_FILE%" 2>nul
del /q "%CORE_HEALTH_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\support_resp_%RANDOM%.json"
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
