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

set "CLIENT_LOGIN_FILE=%TEMP%\cards_client_login_%RANDOM%.json"
set "CLIENT_LOGIN_BODY=%TEMP%\cards_client_login_body_%RANDOM%.json"
set "CLIENT_VERIFY_FILE=%TEMP%\cards_client_verify_%RANDOM%.txt"
set "LIST_FILE=%TEMP%\cards_list_%RANDOM%.json"
set "DETAIL_FILE=%TEMP%\cards_detail_%RANDOM%.json"
set "BLOCK_FILE=%TEMP%\cards_block_%RANDOM%.json"
set "UNBLOCK_FILE=%TEMP%\cards_unblock_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\cards_core_health_%RANDOM%.json"
set "SEED_SQL_FILE=%TEMP%\cards_seed_%RANDOM%.sql"
set "SEED_LOG=%TEMP%\cards_seed_%RANDOM%.log"
set "VERIFY_SQL_FILE=%TEMP%\cards_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\cards_verify_%RANDOM%.log"

set "CLIENT_TOKEN="
set "CLIENT_ID="
set "CLIENT_AUTH_HEADER="
set "CARD_ID=smoke-card-portal-001"

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

echo [1/8] Login client...
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

echo [2/8] Verify client auth...
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%CLIENT_AUTH_HEADER%" "" "204" "%CLIENT_VERIFY_FILE%" || goto :fail

echo [3/8] Seed one issued card for the client...
> "%SEED_SQL_FILE%" echo SET search_path TO processing_core;
>> "%SEED_SQL_FILE%" echo INSERT INTO cards ^(id, client_id, status, pan_masked, issued_at, expires_at^) VALUES ^('%CARD_ID%', '%CLIENT_ID%', 'ACTIVE', '****1111', timezone^('utc', now^(^)^), '12/30'^) ON CONFLICT ^(id^) DO UPDATE SET client_id = EXCLUDED.client_id, status = EXCLUDED.status, pan_masked = EXCLUDED.pan_masked, issued_at = EXCLUDED.issued_at, expires_at = EXCLUDED.expires_at;
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%SEED_SQL_FILE%" > "%SEED_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] cards seed failed
  type "%SEED_LOG%"
  goto :fail
)

echo [4/8] Load client cards...
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/cards" "%CLIENT_AUTH_HEADER%" "" "200" "%LIST_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; payload=json.loads(Path(r'%LIST_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ids={str(item.get('id')) for item in payload.get('items') or []}; print('%CARD_ID%' in ids)"`) do set "LIST_HAS_CARD=%%t"
if /i not "%LIST_HAS_CARD%"=="True" (
  echo [FAIL] seeded card is missing from client cards list
  goto :fail
)
call :http_request "GET" "%CORE_API_BASE%/api/v1/client/cards/%CARD_ID%" "%CLIENT_AUTH_HEADER%" "" "200" "%DETAIL_FILE%" || goto :fail

echo [5/8] Block seeded card...
call :http_request "POST" "%CORE_API_BASE%/api/v1/client/cards/%CARD_ID%/block" "%CLIENT_AUTH_HEADER%" "" "200" "%BLOCK_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%BLOCK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "BLOCK_STATUS=%%t"
if /i not "%BLOCK_STATUS%"=="BLOCKED" (
  echo [FAIL] block card expected BLOCKED, got %BLOCK_STATUS%
  goto :fail
)

echo [6/8] Unblock seeded card...
call :http_request "POST" "%CORE_API_BASE%/api/v1/client/cards/%CARD_ID%/unblock" "%CLIENT_AUTH_HEADER%" "" "200" "%UNBLOCK_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%UNBLOCK_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('status') or '').upper())"`) do set "UNBLOCK_STATUS=%%t"
if /i not "%UNBLOCK_STATUS%"=="ACTIVE" (
  echo [FAIL] unblock card expected ACTIVE, got %UNBLOCK_STATUS%
  goto :fail
)

echo [7/8] Verify persisted card status...
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CARD_STATUS=' ^|^| status FROM cards WHERE id = '%CARD_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] card verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CARD_STATUS=ACTIVE" "%VERIFY_LOG%" >nul || (
  echo [FAIL] card did not persist ACTIVE status after unblock
  type "%VERIFY_LOG%"
  goto :fail
)

echo [8/8] Cards issue smoke completed.
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
del /q "%LIST_FILE%" 2>nul
del /q "%DETAIL_FILE%" 2>nul
del /q "%BLOCK_FILE%" 2>nul
del /q "%UNBLOCK_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\cards_resp_%RANDOM%.json"
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
