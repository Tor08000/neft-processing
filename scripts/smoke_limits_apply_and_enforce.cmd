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

set "CLIENT_LOGIN_FILE=%TEMP%\limits_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\limits_client_login_body_%RANDOM%.json"
set "CLIENT_VERIFY_FILE=%TEMP%\limits_client_verify_%RANDOM%.txt"
set "DETAIL_FILE=%TEMP%\limits_detail_%RANDOM%.json"
set "UPDATE_BODY_FILE=%TEMP%\limits_update_body_%RANDOM%.json"
set "UPDATE_FILE=%TEMP%\limits_update_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\limits_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\limits_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\limits_seed_%RANDOM%.log"
set "VERIFY_SQL_FILE=%TEMP%\limits_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\limits_verify_%RANDOM%.log"

set "CLIENT_TOKEN="
set "CLIENT_ID="
set "CLIENT_AUTH_HEADER="
set "CARD_ID=smoke-card-limit-001"

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

echo [2/7] Verify client auth...
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%CLIENT_AUTH_HEADER%" "" "204" "%CLIENT_VERIFY_FILE%" || goto :fail

echo [3/7] Seed one client card for limit management...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo INSERT INTO cards ^(id, client_id, status, pan_masked, issued_at, expires_at^) VALUES ^('%CARD_ID%', '%CLIENT_ID%', 'ACTIVE', '****2222', timezone^('utc', now^(^)^), '12/30'^) ON CONFLICT ^(id^) DO UPDATE SET client_id = EXCLUDED.client_id, status = EXCLUDED.status, pan_masked = EXCLUDED.pan_masked, issued_at = EXCLUDED.issued_at, expires_at = EXCLUDED.expires_at;
>> "%SEED_SQL_FILE%" echo DELETE FROM limit_configs WHERE scope = 'CARD' AND subject_ref = '%CARD_ID%' AND limit_type = 'DAILY_AMOUNT';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] limit seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/7] Apply card limit via client portal route...
python -c "import json; from pathlib import Path; Path(r'%UPDATE_BODY_FILE%').write_text(json.dumps({'type':'DAILY_AMOUNT','value':2500,'window':'DAILY'}), encoding='utf-8')"
call :http_request "POST" "%CORE_API_BASE%/api/v1/client/cards/%CARD_ID%/limits" "%CLIENT_AUTH_HEADER%" "%UPDATE_BODY_FILE%" "200" "%UPDATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%UPDATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); limits=data.get('limits') or []; ok=bool(limits) and str(limits[0].get('type') or '') == 'DAILY_AMOUNT' and int(limits[0].get('value') or 0) == 2500 and str(limits[0].get('window') or '') == 'DAILY'; print(ok)"`) do set "UPDATE_OK=%%t"
if /i not "%UPDATE_OK%"=="True" (
  echo [FAIL] limit update response did not contain the expected DAILY_AMOUNT limit
  type "%UPDATE_FILE%"
  goto :fail
)

echo [5/7] Verify card detail reflects the applied limit...
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/cards/%CARD_ID%" "%CLIENT_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%DETAIL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); limits=data.get('limits') or []; ok=bool(limits) and int(limits[0].get('value') or 0) == 2500; print(ok)"`) do set "DETAIL_OK=%%t"
if /i not "%DETAIL_OK%"=="True" (
  echo [FAIL] card detail did not reflect the applied limit
  type "%DETAIL_FILE%"
  goto :fail
)

echo [6/7] Verify persisted limit row...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'LIMIT_VALUE=' ^|^| value::text FROM limit_configs WHERE scope = 'CARD' AND subject_ref = '%CARD_ID%' AND limit_type = 'DAILY_AMOUNT';
>> "%VERIFY_SQL_FILE%" echo SELECT 'LIMIT_WINDOW=' ^|^| "window"::text FROM limit_configs WHERE scope = 'CARD' AND subject_ref = '%CARD_ID%' AND limit_type = 'DAILY_AMOUNT';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] limit verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"LIMIT_VALUE=2500" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted limit value is not 2500
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"LIMIT_WINDOW=DAILY" "%VERIFY_LOG%" >nul || (
  echo [FAIL] persisted limit window is not DAILY
  type "%VERIFY_LOG%"
  goto :fail
)

echo [7/7] Limits apply smoke completed.
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
del /q "%DETAIL_FILE%" 2>nul
del /q "%UPDATE_BODY_FILE%" 2>nul
del /q "%UPDATE_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\limits_resp_%RANDOM%.json"
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
