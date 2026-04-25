@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "ADMIN_LEGAL_ROOT=%CORE_ROOT%/v1/admin/legal"

set "ADMIN_LOGIN_FILE=%TEMP%\partner_onboarding_admin_login_%RANDOM%.json"
set "ADMIN_LOGIN_BODY=%TEMP%\partner_onboarding_admin_login_body_%RANDOM%.json"
set "PARTNER_LOGIN_FILE=%TEMP%\partner_onboarding_partner_login_%RANDOM%.json"
set "PARTNER_LOGIN_BODY=%TEMP%\partner_onboarding_partner_login_body_%RANDOM%.json"
set "ADMIN_VERIFY_FILE=%TEMP%\partner_onboarding_admin_verify_%RANDOM%.txt"
set "PARTNER_VERIFY_FILE=%TEMP%\partner_onboarding_partner_verify_%RANDOM%.txt"
set "PORTAL_ME_FILE=%TEMP%\partner_onboarding_portal_me_%RANDOM%.json"
set "RESET_PORTAL_FILE=%TEMP%\partner_onboarding_reset_portal_%RANDOM%.json"
set "SNAPSHOT_FILE=%TEMP%\partner_onboarding_snapshot_%RANDOM%.json"
set "PROFILE_BODY_FILE=%TEMP%\partner_onboarding_profile_body_%RANDOM%.json"
set "PROFILE_FILE=%TEMP%\partner_onboarding_profile_%RANDOM%.json"
set "LEGAL_PROFILE_BODY=%TEMP%\partner_onboarding_legal_profile_body_%RANDOM%.json"
set "LEGAL_PROFILE_FILE=%TEMP%\partner_onboarding_legal_profile_%RANDOM%.json"
set "LEGAL_DETAILS_BODY=%TEMP%\partner_onboarding_legal_details_body_%RANDOM%.json"
set "LEGAL_DETAILS_FILE=%TEMP%\partner_onboarding_legal_details_%RANDOM%.json"
set "LEGAL_REQUIRED_FILE=%TEMP%\partner_onboarding_legal_required_%RANDOM%.json"
set "LEGAL_ACCEPT_QUEUE=%TEMP%\partner_onboarding_legal_accept_%RANDOM%.txt"
set "LEGAL_ACCEPT_BODY=%TEMP%\partner_onboarding_legal_accept_body_%RANDOM%.json"
set "PRE_ACTIVATE_FILE=%TEMP%\partner_onboarding_pre_activate_%RANDOM%.json"
set "ADMIN_STATUS_BODY=%TEMP%\partner_onboarding_admin_status_body_%RANDOM%.json"
set "ADMIN_STATUS_FILE=%TEMP%\partner_onboarding_admin_status_%RANDOM%.json"
set "ACTIVATE_FILE=%TEMP%\partner_onboarding_activate_%RANDOM%.json"
set "FINAL_PORTAL_FILE=%TEMP%\partner_onboarding_final_portal_%RANDOM%.json"
set "VERIFY_SQL_FILE=%TEMP%\partner_onboarding_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\partner_onboarding_verify_%RANDOM%.log"
set "RESET_SQL_FILE=%TEMP%\partner_onboarding_reset_%RANDOM%.sql"
set "RESET_LOG=%TEMP%\partner_onboarding_reset_%RANDOM%.log"
set "CORE_HEALTH_FILE=%TEMP%\partner_onboarding_core_health_%RANDOM%.json"

set "ADMIN_TOKEN="
set "PARTNER_TOKEN="
set "PARTNER_ID="
set "ADMIN_AUTH_HEADER="
set "PARTNER_AUTH_HEADER="
set "PENDING_DOCS=0"

echo [0/11] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/11] Check auth + core surfaces...
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

echo [1/11] Login admin...
python -c "import json; from pathlib import Path; Path(r'%ADMIN_LOGIN_BODY%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  goto :fail
)
set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
if /i "%ADMIN_TOKEN:~0,7%"=="Bearer " set "ADMIN_AUTH_HEADER=Authorization: %ADMIN_TOKEN%"

echo [2/11] Login partner...
python -c "import json; from pathlib import Path; Path(r'%PARTNER_LOGIN_BODY%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','password': r'%PARTNER_PASSWORD%','portal':'partner'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%PARTNER_LOGIN_BODY%" "200" "%PARTNER_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%t"
if "%PARTNER_TOKEN%"=="" (
  echo [FAIL] partner login missing access_token
  goto :fail
)
set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
if /i "%PARTNER_TOKEN:~0,7%"=="Bearer " set "PARTNER_AUTH_HEADER=Authorization: %PARTNER_TOKEN%"

echo [3/11] Verify admin and partner auth...
call :http_request "GET" "%CORE_ROOT%/admin/auth/verify" "%ADMIN_AUTH_HEADER%" "" "204" "%ADMIN_VERIFY_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/partner/auth/verify" "%PARTNER_AUTH_HEADER%" "" "204" "%PARTNER_VERIFY_FILE%" || goto :fail

echo [4/11] Resolve partner context...
call :http_request "GET" "%CORE_ROOT%/portal/me" "%PARTNER_AUTH_HEADER%" "" "200" "%PORTAL_ME_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_ME_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); partner=data.get('partner') or {}; org=data.get('org') or {}; print(partner.get('partner_id') or org.get('id') or '')"`) do set "PARTNER_ID=%%t"
if "%PARTNER_ID%"=="" (
  echo [FAIL] partner portal/me did not return partner context
  goto :fail
)

echo [5/11] Reset partner into onboarding state...
> "%RESET_SQL_FILE%" echo SET search_path TO processing_core;
>> "%RESET_SQL_FILE%" echo UPDATE partners SET status = 'PENDING', brand_name = NULL, contacts = '{}'::jsonb WHERE id = '%PARTNER_ID%';
>> "%RESET_SQL_FILE%" echo DELETE FROM partner_legal_profiles WHERE partner_id = '%PARTNER_ID%';
>> "%RESET_SQL_FILE%" echo DELETE FROM partner_legal_details WHERE partner_id = '%PARTNER_ID%';
>> "%RESET_SQL_FILE%" echo DELETE FROM legal_acceptances WHERE subject_type = 'PARTNER' AND subject_id = '%PARTNER_ID%';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 < "%RESET_SQL_FILE%" > "%RESET_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] partner onboarding reset failed
  type "%RESET_LOG%"
  goto :fail
)

echo [6/11] Verify mounted onboarding owner state...
call :http_request "GET" "%CORE_ROOT%/portal/me" "%PARTNER_AUTH_HEADER%" "" "200" "%RESET_PORTAL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESET_PORTAL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); partner=data.get('partner') or {}; ok=data.get('access_state') == 'NEEDS_ONBOARDING' and data.get('access_reason') == 'partner_onboarding' and str(partner.get('status') or '').upper() == 'PENDING'; print(ok)"`) do set "RESET_PORTAL_OK=%%t"
if /i not "%RESET_PORTAL_OK%"=="True" (
  echo [FAIL] portal/me did not expose mounted partner_onboarding owner state
  type "%RESET_PORTAL_FILE%"
  goto :fail
)
call :http_request "GET" "%CORE_ROOT%/partner/onboarding" "%PARTNER_AUTH_HEADER%" "" "200" "%SNAPSHOT_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%SNAPSHOT_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); checklist=data.get('checklist') or {}; reasons={str(item) for item in (checklist.get('blocked_reasons') or [])}; ok=checklist.get('activation_ready') is False and checklist.get('next_route') == '/onboarding' and 'profile_incomplete' in reasons; print(ok)"`) do set "SNAPSHOT_OK=%%t"
if /i not "%SNAPSHOT_OK%"=="True" (
  echo [FAIL] onboarding snapshot did not expose the expected blocked state
  type "%SNAPSHOT_FILE%"
  goto :fail
)

echo [7/11] Complete partner-owned onboarding steps...
python -c "import json; from pathlib import Path; Path(r'%PROFILE_BODY_FILE%').write_text(json.dumps({'brand_name':'Smoke Partner','contacts':{'email':'owner@partner.test','phone':'+7 900 000 00 00'}}), encoding='utf-8')"
call :http_request "PATCH" "%CORE_ROOT%/partner/onboarding/profile" "%PARTNER_AUTH_HEADER%" "%PROFILE_BODY_FILE%" "200" "%PROFILE_FILE%" || goto :fail
python -c "import json; from pathlib import Path; Path(r'%LEGAL_PROFILE_BODY%').write_text(json.dumps({'legal_type':'LEGAL_ENTITY','country':'RU','tax_residency':'RU','tax_regime':'USN','vat_applicable':False,'vat_rate':None}), encoding='utf-8')"
call :http_request "PUT" "%CORE_ROOT%/partner/legal/profile" "%PARTNER_AUTH_HEADER%" "%LEGAL_PROFILE_BODY%" "200" "%LEGAL_PROFILE_FILE%" || goto :fail
python -c "import json; from pathlib import Path; Path(r'%LEGAL_DETAILS_BODY%').write_text(json.dumps({'legal_name':'Smoke Partner LLC','inn':'7701234567','kpp':'770101001','ogrn':'1027700000000','bank_account':'40702810900000000001','bank_bic':'044525225','bank_name':'Neft Bank'}), encoding='utf-8')"
call :http_request "PUT" "%CORE_ROOT%/partner/legal/details" "%PARTNER_AUTH_HEADER%" "%LEGAL_DETAILS_BODY%" "200" "%LEGAL_DETAILS_FILE%" || goto :fail
call :http_request "GET" "%CORE_ROOT%/legal/required" "%PARTNER_AUTH_HEADER%" "" "200" "%LEGAL_REQUIRED_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LEGAL_REQUIRED_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=[item for item in (data.get('required') or []) if not item.get('accepted')]; Path(r'%LEGAL_ACCEPT_QUEUE%').write_text('\\n'.join(f\"{item['code']};{item['required_version']};{item['locale']}\" for item in items), encoding='utf-8'); print(len(items))"`) do set "PENDING_DOCS=%%t"
if not "%PENDING_DOCS%"=="0" (
  for /f "usebackq tokens=1,2,3 delims=;" %%a in ("%LEGAL_ACCEPT_QUEUE%") do (
    python -c "import json; from pathlib import Path; Path(r'%LEGAL_ACCEPT_BODY%').write_text(json.dumps({'code':r'%%a','version':r'%%b','locale':r'%%c','accepted':True}), encoding='utf-8')"
    call :http_request "POST" "%CORE_ROOT%/legal/accept" "%PARTNER_AUTH_HEADER%" "%LEGAL_ACCEPT_BODY%" "204" "%LEGAL_ACCEPT_BODY%.out" || goto :fail
  )
)

echo [8/11] Verify activation stays blocked before admin review...
call :http_request "POST" "%CORE_ROOT%/partner/onboarding/activate" "%PARTNER_AUTH_HEADER%" "" "409" "%PRE_ACTIVATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PRE_ACTIVATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); payload=data.get('detail') if isinstance(data.get('detail'), dict) else data; reasons={str(item) for item in (payload.get('blocked_reasons') or [])}; ok=payload.get('error') == 'partner_onboarding_incomplete' and 'legal_review_pending' in reasons; print(ok)"`) do set "PRE_ACTIVATE_OK=%%t"
if /i not "%PRE_ACTIVATE_OK%"=="True" (
  echo [FAIL] activation should remain blocked before admin verification
  type "%PRE_ACTIVATE_FILE%"
  goto :fail
)

echo [9/11] Verify legal profile as admin...
python -c "import json; from pathlib import Path; Path(r'%ADMIN_STATUS_BODY%').write_text(json.dumps({'status':'VERIFIED','reason':'smoke onboarding verification'}), encoding='utf-8')"
call :http_request "POST" "%ADMIN_LEGAL_ROOT%/partners/%PARTNER_ID%/status" "%ADMIN_AUTH_HEADER%" "%ADMIN_STATUS_BODY%" "200" "%ADMIN_STATUS_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_STATUS_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(str(data.get('legal_status') or '').upper() == 'VERIFIED')"`) do set "ADMIN_STATUS_OK=%%t"
if /i not "%ADMIN_STATUS_OK%"=="True" (
  echo [FAIL] admin legal verification did not return VERIFIED
  type "%ADMIN_STATUS_FILE%"
  goto :fail
)

echo [10/11] Activate partner...
call :http_request "POST" "%CORE_ROOT%/partner/onboarding/activate" "%PARTNER_AUTH_HEADER%" "" "200" "%ACTIVATE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ACTIVATE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); checklist=data.get('checklist') or {}; partner=data.get('partner') or {}; ok=str(partner.get('status') or '').upper() == 'ACTIVE' and checklist.get('activation_ready') is True; print(ok)"`) do set "ACTIVATE_OK=%%t"
if /i not "%ACTIVATE_OK%"=="True" (
  echo [FAIL] activation response did not return ACTIVE partner state
  type "%ACTIVATE_FILE%"
  goto :fail
)

echo [11/11] Verify final portal and DB truth...
call :http_request "GET" "%CORE_ROOT%/portal/me" "%PARTNER_AUTH_HEADER%" "" "200" "%FINAL_PORTAL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%FINAL_PORTAL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=data.get('access_state') == 'ACTIVE' and data.get('access_reason') in (None, '', 'ok'); print(ok)"`) do set "FINAL_PORTAL_OK=%%t"
if /i not "%FINAL_PORTAL_OK%"=="True" (
  echo [FAIL] final portal/me did not reach ACTIVE state
  type "%FINAL_PORTAL_FILE%"
  goto :fail
)
> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'PARTNER_STATUS=' ^|^| status::text FROM partners WHERE id = '%PARTNER_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'LEGAL_STATUS=' ^|^| legal_status::text FROM partner_legal_profiles WHERE partner_id = '%PARTNER_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'LEGAL_ACCEPTANCES=' ^|^| count^(*^)::text FROM legal_acceptances WHERE subject_type = 'PARTNER' AND subject_id = '%PARTNER_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUDIT_STARTED=' ^|^| count^(*^)::text FROM audit_log WHERE entity_type = 'partner' AND entity_id = '%PARTNER_ID%' AND event_type = 'PARTNER_ONBOARDING_STARTED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUDIT_PROFILE_UPDATED=' ^|^| count^(*^)::text FROM audit_log WHERE entity_type = 'partner' AND entity_id = '%PARTNER_ID%' AND event_type = 'PARTNER_ONBOARDING_PROFILE_UPDATED';
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUDIT_ACTIVATED=' ^|^| count^(*^)::text FROM audit_log WHERE entity_type = 'partner' AND entity_id = '%PARTNER_ID%' AND event_type = 'PARTNER_ACTIVATED';
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] partner onboarding verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"PARTNER_STATUS=ACTIVE" "%VERIFY_LOG%" >nul || (
  echo [FAIL] partner row did not persist ACTIVE status
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"LEGAL_STATUS=VERIFIED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] partner legal profile did not persist VERIFIED status
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"AUDIT_STARTED=[1-9][0-9]*" "%VERIFY_LOG%" >nul || (
  echo [FAIL] onboarding start audit event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"AUDIT_PROFILE_UPDATED=[1-9][0-9]*" "%VERIFY_LOG%" >nul || (
  echo [FAIL] onboarding profile update audit event missing
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /r /c:"AUDIT_ACTIVATED=[1-9][0-9]*" "%VERIFY_LOG%" >nul || (
  echo [FAIL] activation audit event missing
  type "%VERIFY_LOG%"
  goto :fail
)
if not "%PENDING_DOCS%"=="0" (
  findstr /r /c:"LEGAL_ACCEPTANCES=[1-9][0-9]*" "%VERIFY_LOG%" >nul || (
    echo [FAIL] legal acceptances were expected but not persisted
    type "%VERIFY_LOG%"
    goto :fail
  )
)

echo [SMOKE] Partner onboarding smoke completed.
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
del /q "%PARTNER_LOGIN_FILE%" 2>nul
del /q "%PARTNER_LOGIN_BODY%" 2>nul
del /q "%ADMIN_VERIFY_FILE%" 2>nul
del /q "%PARTNER_VERIFY_FILE%" 2>nul
del /q "%PORTAL_ME_FILE%" 2>nul
del /q "%RESET_PORTAL_FILE%" 2>nul
del /q "%SNAPSHOT_FILE%" 2>nul
del /q "%PROFILE_BODY_FILE%" 2>nul
del /q "%PROFILE_FILE%" 2>nul
del /q "%LEGAL_PROFILE_BODY%" 2>nul
del /q "%LEGAL_PROFILE_FILE%" 2>nul
del /q "%LEGAL_DETAILS_BODY%" 2>nul
del /q "%LEGAL_DETAILS_FILE%" 2>nul
del /q "%LEGAL_REQUIRED_FILE%" 2>nul
del /q "%LEGAL_ACCEPT_QUEUE%" 2>nul
del /q "%LEGAL_ACCEPT_BODY%" 2>nul
del /q "%LEGAL_ACCEPT_BODY%.out" 2>nul
del /q "%PRE_ACTIVATE_FILE%" 2>nul
del /q "%ADMIN_STATUS_BODY%" 2>nul
del /q "%ADMIN_STATUS_FILE%" 2>nul
del /q "%ACTIVATE_FILE%" 2>nul
del /q "%FINAL_PORTAL_FILE%" 2>nul
del /q "%VERIFY_SQL_FILE%" 2>nul
del /q "%VERIFY_LOG%" 2>nul
del /q "%RESET_SQL_FILE%" 2>nul
del /q "%RESET_LOG%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\partner_onboarding_resp_%RANDOM%.json"
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
