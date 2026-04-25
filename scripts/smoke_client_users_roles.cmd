@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
if "%POSTGRES_PASSWORD%"=="" set "POSTGRES_PASSWORD=change-me"

set "AUTH_URL=%AUTH_HOST_BASE%%AUTH_BASE%"
set "CORE_ROOT=%CORE_API_BASE%%CORE_BASE%"
set "SMOKE_EMAIL=client-users-%RANDOM%%RANDOM%@neft.local"
set "SMOKE_PASSWORD=NeftSmoke123!"
set "SMOKE_FULL_NAME=Client Users Smoke"

set "REGISTER_FILE=%TEMP%\client_users_register_%RANDOM%.json"
set "REGISTER_BODY_FILE=%TEMP%\client_users_register_body_%RANDOM%.json"
set "VERIFY_FILE=%TEMP%\client_users_verify_%RANDOM%.json"
set "ME_FILE=%TEMP%\client_users_me_%RANDOM%.json"
set "LOGIN_FILE=%TEMP%\client_users_login_%RANDOM%.json"
set "LOGIN_BODY_FILE=%TEMP%\client_users_login_body_%RANDOM%.json"
set "CORE_VERIFY_FILE=%TEMP%\client_users_core_verify_%RANDOM%.txt"
set "PORTAL_ME_FILE=%TEMP%\client_users_portal_me_%RANDOM%.json"
set "USERS_FILE=%TEMP%\client_users_list_%RANDOM%.json"
set "ROLE_BODY_FILE=%TEMP%\client_users_role_body_%RANDOM%.json"
set "ROLE_FILE=%TEMP%\client_users_role_%RANDOM%.json"
set "USERS_AFTER_ROLE_FILE=%TEMP%\client_users_list_after_role_%RANDOM%.json"
set "INVITE_BODY_FILE=%TEMP%\client_users_invite_body_%RANDOM%.json"
set "INVITE_FILE=%TEMP%\client_users_invite_%RANDOM%.json"
set "INVITATIONS_FILE=%TEMP%\client_users_invitations_%RANDOM%.json"
set "RESEND_BODY_FILE=%TEMP%\client_users_resend_body_%RANDOM%.json"
set "RESEND_FILE=%TEMP%\client_users_resend_%RANDOM%.json"
set "REVOKE_BODY_FILE=%TEMP%\client_users_revoke_body_%RANDOM%.json"
set "REVOKE_FILE=%TEMP%\client_users_revoke_%RANDOM%.json"
set "REVOKE_AGAIN_FILE=%TEMP%\client_users_revoke_again_%RANDOM%.json"
set "CORE_HEALTH_FILE=%TEMP%\client_users_core_health_%RANDOM%.json"
set "VERIFY_SQL_FILE=%TEMP%\client_users_verify_%RANDOM%.sql"
set "VERIFY_LOG=%TEMP%\client_users_verify_%RANDOM%.log"

set "REGISTER_TOKEN="
set "LOGIN_TOKEN="
set "REGISTER_USER_ID="
set "CLIENT_ID="
set "INVITATION_ID="
set "REGISTER_AUTH_HEADER="
set "LOGIN_AUTH_HEADER="
set "SMOKE_INVITE_EMAIL=client-invite-%RANDOM%%RANDOM%@neft.local"

echo [0/12] Check docker compose postgres...
docker compose ps postgres >nul 2>&1
if errorlevel 1 (
  echo [FAIL] docker compose postgres unavailable. Start Docker Desktop and the NEFT core stack.
  goto :fail
)

echo [0.1/12] Check auth + core surfaces...
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

echo [1/12] Register a new client identity...
python -c "import json; from pathlib import Path; Path(r'%REGISTER_BODY_FILE%').write_text(json.dumps({'email': r'%SMOKE_EMAIL%','password': r'%SMOKE_PASSWORD%','full_name': r'%SMOKE_FULL_NAME%'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/register" "" "%REGISTER_BODY_FILE%" "201" "%REGISTER_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REGISTER_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "REGISTER_TOKEN=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REGISTER_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "REGISTER_USER_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REGISTER_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('client_id',''))"`) do set "CLIENT_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REGISTER_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles={str(role).upper() for role in (data.get('roles') or [])}; ok=data.get('subject_type') == 'client_user' and 'CLIENT_OWNER' in roles and bool(data.get('client_id')); print(ok)"`) do set "REGISTER_OK=%%t"
if "%REGISTER_TOKEN%"=="" (
  echo [FAIL] register response missing access_token
  goto :fail
)
if "%REGISTER_USER_ID%"=="" (
  echo [FAIL] register response missing user id
  goto :fail
)
if "%CLIENT_ID%"=="" (
  echo [FAIL] register response missing client_id
  goto :fail
)
if /i not "%REGISTER_OK%"=="True" (
  echo [FAIL] register response missing client_user / CLIENT_OWNER bootstrap truth
  type "%REGISTER_FILE%"
  goto :fail
)
set "REGISTER_AUTH_HEADER=Authorization: Bearer %REGISTER_TOKEN%"
if /i "%REGISTER_TOKEN:~0,7%"=="Bearer " set "REGISTER_AUTH_HEADER=Authorization: %REGISTER_TOKEN%"

echo [2/12] Verify signup token...
call :http_request "GET" "%AUTH_URL%/verify" "%REGISTER_AUTH_HEADER%" "" "200" "%VERIFY_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%VERIFY_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=data.get('valid') is True and data.get('portal') == 'client' and str(data.get('user_id') or '') == r'%REGISTER_USER_ID%'; print(ok)"`) do set "VERIFY_OK=%%t"
if /i not "%VERIFY_OK%"=="True" (
  echo [FAIL] auth verify did not confirm the signup token
  type "%VERIFY_FILE%"
  goto :fail
)

echo [3/12] Fetch auth identity profile...
call :http_request "GET" "%AUTH_URL%/me" "%REGISTER_AUTH_HEADER%" "" "200" "%ME_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ME_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles={str(role).upper() for role in (data.get('roles') or [])}; ok=data.get('email') == r'%SMOKE_EMAIL%' and data.get('subject_type') == 'client_user' and str(data.get('user_id') or '') == r'%REGISTER_USER_ID%' and str(data.get('client_id') or '') == r'%CLIENT_ID%' and 'CLIENT_OWNER' in roles; print(ok)"`) do set "ME_OK=%%t"
if /i not "%ME_OK%"=="True" (
  echo [FAIL] auth me did not return the expected client identity payload
  type "%ME_FILE%"
  goto :fail
)

echo [4/12] Login with the newly registered user...
python -c "import json; from pathlib import Path; Path(r'%LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%SMOKE_EMAIL%','password': r'%SMOKE_PASSWORD%','portal':'client'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%LOGIN_BODY_FILE%" "200" "%LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "LOGIN_TOKEN=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles={str(role).upper() for role in (data.get('roles') or [])}; ok=data.get('email') == r'%SMOKE_EMAIL%' and data.get('subject_type') == 'client_user' and 'CLIENT_OWNER' in roles; print(ok)"`) do set "LOGIN_OK=%%t"
if "%LOGIN_TOKEN%"=="" (
  echo [FAIL] login response missing access_token
  goto :fail
)
if /i not "%LOGIN_OK%"=="True" (
  echo [FAIL] login response did not preserve client owner identity truth
  type "%LOGIN_FILE%"
  goto :fail
)
set "LOGIN_AUTH_HEADER=Authorization: Bearer %LOGIN_TOKEN%"
if /i "%LOGIN_TOKEN:~0,7%"=="Bearer " set "LOGIN_AUTH_HEADER=Authorization: %LOGIN_TOKEN%"

echo [5/12] Verify client auth in processing-core...
call :http_request "GET" "%CORE_ROOT%/client/auth/verify" "%LOGIN_AUTH_HEADER%" "" "204" "%CORE_VERIFY_FILE%" || goto :fail

echo [6/12] Resolve client portal context...
call :http_request "GET" "%CORE_ROOT%/portal/me" "%LOGIN_AUTH_HEADER%" "" "200" "%PORTAL_ME_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PORTAL_ME_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); org=data.get('org') or {}; user_roles={str(role).upper() for role in (data.get('user_roles') or [])}; flags=data.get('flags') or {}; ok=bool(org) and str(org.get('id') or '') == r'%CLIENT_ID%' and bool(str(data.get('org_status') or '')) and 'CLIENT_OWNER' in user_roles and flags.get('portal_me_failed') is not True; print(ok)"`) do set "PORTAL_OK=%%t"
if /i not "%PORTAL_OK%"=="True" (
  echo [FAIL] portal/me did not resolve the newly registered client context
  type "%PORTAL_ME_FILE%"
  goto :fail
)

echo [7/12] Verify users list owner surface...
call :http_request "GET" "%CORE_ROOT%/client/users" "%LOGIN_AUTH_HEADER%" "" "200" "%USERS_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%USERS_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=data.get('items') or []; ok=any(str(item.get('user_id') or '') == r'%REGISTER_USER_ID%' and 'CLIENT_OWNER' in {str(role).upper() for role in (item.get('roles') or [])} for item in items); print(ok)"`) do set "USERS_OK=%%t"
if /i not "%USERS_OK%"=="True" (
  echo [FAIL] client users list did not expose the bootstrap owner membership
  type "%USERS_FILE%"
  goto :fail
)

echo [8/12] Verify user role update surface...
python -c "import json; from pathlib import Path; Path(r'%ROLE_BODY_FILE%').write_text(json.dumps({'roles':['CLIENT_OWNER','CLIENT_MANAGER']}), encoding='utf-8')"
call :http_request "POST" "%CORE_ROOT%/client/users/%REGISTER_USER_ID%/roles" "%LOGIN_AUTH_HEADER%" "%ROLE_BODY_FILE%" "200" "%ROLE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ROLE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); roles={str(role).upper() for role in (data.get('roles') or [])}; ok=data.get('status') == 'ok' and str(data.get('user_id') or '') == r'%REGISTER_USER_ID%' and {'CLIENT_OWNER','CLIENT_MANAGER'}.issubset(roles); print(ok)"`) do set "ROLE_OK=%%t"
if /i not "%ROLE_OK%"=="True" (
  echo [FAIL] role update did not persist CLIENT_OWNER + CLIENT_MANAGER for the owner membership
  type "%ROLE_FILE%"
  goto :fail
)
call :http_request "GET" "%CORE_ROOT%/client/users" "%LOGIN_AUTH_HEADER%" "" "200" "%USERS_AFTER_ROLE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%USERS_AFTER_ROLE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=data.get('items') or []; ok=any(str(item.get('user_id') or '') == r'%REGISTER_USER_ID%' and {'CLIENT_OWNER','CLIENT_MANAGER'}.issubset({str(role).upper() for role in (item.get('roles') or [])}) for item in items); print(ok)"`) do set "ROLE_LIST_OK=%%t"
if /i not "%ROLE_LIST_OK%"=="True" (
  echo [FAIL] users list did not reflect the updated owner role set
  type "%USERS_AFTER_ROLE_FILE%"
  goto :fail
)

echo [9/12] Create a client invitation...
python -c "import json; from pathlib import Path; Path(r'%INVITE_BODY_FILE%').write_text(json.dumps({'email': r'%SMOKE_INVITE_EMAIL%','roles':['CLIENT_MANAGER']}), encoding='utf-8')"
call :http_request "POST" "%CORE_ROOT%/client/users/invite" "%LOGIN_AUTH_HEADER%" "%INVITE_BODY_FILE%" "201" "%INVITE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%INVITE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('invitation_id',''))"`) do set "INVITATION_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%INVITE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=data.get('status') == 'PENDING' and data.get('email') == r'%SMOKE_INVITE_EMAIL%' and bool(data.get('invitation_id')); print(ok)"`) do set "INVITE_OK=%%t"
if "%INVITATION_ID%"=="" (
  echo [FAIL] invite response missing invitation_id
  type "%INVITE_FILE%"
  goto :fail
)
if /i not "%INVITE_OK%"=="True" (
  echo [FAIL] invite response did not return the expected pending invitation payload
  type "%INVITE_FILE%"
  goto :fail
)

echo [10/12] Verify invitation list and resend flow...
call :http_request "GET" "%CORE_ROOT%/client/users/invitations?status=PENDING&q=%SMOKE_INVITE_EMAIL%&sort=created_at_desc&limit=10&offset=0" "%LOGIN_AUTH_HEADER%" "" "200" "%INVITATIONS_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%INVITATIONS_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); items=data.get('items') or []; ok=any(str(item.get('invitation_id') or '') == r'%INVITATION_ID%' and item.get('email') == r'%SMOKE_INVITE_EMAIL%' and item.get('status') == 'PENDING' for item in items); print(ok)"`) do set "INVITATIONS_OK=%%t"
if /i not "%INVITATIONS_OK%"=="True" (
  echo [FAIL] invitations list did not expose the new pending invitation
  type "%INVITATIONS_FILE%"
  goto :fail
)
python -c "import json; from pathlib import Path; Path(r'%RESEND_BODY_FILE%').write_text(json.dumps({'expires_in_days': 7}), encoding='utf-8')"
call :http_request "POST" "%CORE_ROOT%/client/users/invitations/%INVITATION_ID%/resend" "%LOGIN_AUTH_HEADER%" "%RESEND_BODY_FILE%" "200" "%RESEND_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%RESEND_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); ok=data.get('status') == 'PENDING' and int(data.get('resent_count') or 0) == 1; print(ok)"`) do set "RESEND_OK=%%t"
if /i not "%RESEND_OK%"=="True" (
  echo [FAIL] invitation resend did not return the expected pending/resent payload
  type "%RESEND_FILE%"
  goto :fail
)

echo [11/12] Verify invitation revoke conflict semantics...
python -c "import json; from pathlib import Path; Path(r'%REVOKE_BODY_FILE%').write_text(json.dumps({'reason': 'smoke'}), encoding='utf-8')"
call :http_request "POST" "%CORE_ROOT%/client/users/invitations/%INVITATION_ID%/revoke" "%LOGIN_AUTH_HEADER%" "%REVOKE_BODY_FILE%" "200" "%REVOKE_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%REVOKE_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('status',''))"`) do set "REVOKE_STATUS=%%t"
if /i not "%REVOKE_STATUS%"=="REVOKED" (
  echo [FAIL] invitation revoke did not return REVOKED
  type "%REVOKE_FILE%"
  goto :fail
)
call :http_request "POST" "%CORE_ROOT%/client/users/invitations/%INVITATION_ID%/revoke" "%LOGIN_AUTH_HEADER%" "" "409" "%REVOKE_AGAIN_FILE%" || goto :fail

echo [12/12] Verify auth/core storage linkage...
> "%VERIFY_SQL_FILE%" echo SET search_path TO public;
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUTH_USER=' ^|^| id::text FROM users WHERE lower^(email^) = lower^('%SMOKE_EMAIL%'^);
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUTH_ROLE=' ^|^| role_code FROM user_roles ur JOIN users u ON ur.user_id = u.id WHERE lower^(u.email^) = lower^('%SMOKE_EMAIL%'^) ORDER BY role_code;
>> "%VERIFY_SQL_FILE%" echo SELECT 'AUTH_LINK=' ^|^| uc.client_id::text FROM user_clients uc JOIN users u ON uc.user_id = u.id WHERE lower^(u.email^) = lower^('%SMOKE_EMAIL%'^);
>> "%VERIFY_SQL_FILE%" echo SET search_path TO processing_core;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_CLIENT=' ^|^| id::text FROM clients WHERE id = '%CLIENT_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_CLIENT_STATUS=' ^|^| status::text FROM clients WHERE id = '%CLIENT_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_ONBOARDING=' ^|^| status::text FROM client_onboarding WHERE client_id = '%CLIENT_ID%' AND owner_user_id = '%REGISTER_USER_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_ROLE_ROW=' ^|^| roles::text FROM client_user_roles WHERE client_id = '%CLIENT_ID%' AND user_id = '%REGISTER_USER_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_INVITE_ID=' ^|^| id::text FROM client_invitations WHERE id = '%INVITATION_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_INVITE_STATUS=' ^|^| status FROM client_invitations WHERE id = '%INVITATION_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_INVITE_REVOKED_BY=' ^|^| COALESCE(revoked_by_user_id,'') FROM client_invitations WHERE id = '%INVITATION_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_INVITE_RESENT=' ^|^| COALESCE(resent_count,0)::text FROM client_invitations WHERE id = '%INVITATION_ID%';
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_INVITE_DELIVERY=' ^|^| status FROM invitation_email_deliveries WHERE invitation_id = '%INVITATION_ID%' ORDER BY created_at DESC LIMIT 1;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_OUTBOX_SUBJECT=' ^|^| subject_type::text FROM notification_outbox WHERE aggregate_id = '%INVITATION_ID%' ORDER BY created_at DESC LIMIT 1;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_OUTBOX_SUBJECT_ID=' ^|^| subject_id::text FROM notification_outbox WHERE aggregate_id = '%INVITATION_ID%' ORDER BY created_at DESC LIMIT 1;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_OUTBOX_TEMPLATE=' ^|^| template_code FROM notification_outbox WHERE aggregate_id = '%INVITATION_ID%' ORDER BY created_at DESC LIMIT 1;
>> "%VERIFY_SQL_FILE%" echo SELECT 'CORE_OUTBOX_DEDUPE=' ^|^| dedupe_key FROM notification_outbox WHERE aggregate_id = '%INVITATION_ID%' ORDER BY created_at DESC LIMIT 1;
docker compose exec -T -e PGPASSWORD=%POSTGRES_PASSWORD% postgres psql -U neft -d neft -v ON_ERROR_STOP=1 -t -A < "%VERIFY_SQL_FILE%" > "%VERIFY_LOG%" 2>&1
if errorlevel 1 (
  echo [FAIL] client users/roles verification query failed
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"AUTH_USER=%REGISTER_USER_ID%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] auth users table did not persist the new user
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"AUTH_ROLE=CLIENT_OWNER" "%VERIFY_LOG%" >nul || (
  echo [FAIL] auth user_roles did not persist CLIENT_OWNER
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"AUTH_LINK=%CLIENT_ID%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] auth user_clients did not link the new user to the new client
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_CLIENT=%CLIENT_ID%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] processing_core clients table did not persist the new client
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_CLIENT_STATUS=ONBOARDING" "%VERIFY_LOG%" >nul || (
  echo [FAIL] processing_core client did not persist ONBOARDING status
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_ONBOARDING=DRAFT" "%VERIFY_LOG%" >nul || (
  echo [FAIL] processing_core client_onboarding did not persist DRAFT bootstrap row
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_ROLE_ROW=" "%VERIFY_LOG%" >nul || (
  echo [FAIL] processing_core client_user_roles did not persist the updated owner role row
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CLIENT_OWNER" "%VERIFY_LOG%" >nul || (
  echo [FAIL] updated owner role row is missing CLIENT_OWNER
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CLIENT_MANAGER" "%VERIFY_LOG%" >nul || (
  echo [FAIL] updated owner role row is missing CLIENT_MANAGER
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_INVITE_ID=%INVITATION_ID%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] processing_core client_invitations did not persist the invitation row
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_INVITE_STATUS=REVOKED" "%VERIFY_LOG%" >nul || (
  echo [FAIL] invitation row did not persist REVOKED status
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_INVITE_REVOKED_BY=%REGISTER_USER_ID%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] invitation row did not persist revoked_by_user_id
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_INVITE_RESENT=1" "%VERIFY_LOG%" >nul || (
  echo [FAIL] invitation row did not persist resent_count=1
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_INVITE_DELIVERY=" "%VERIFY_LOG%" >nul || (
  echo [FAIL] invitation delivery row was not persisted
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_OUTBOX_SUBJECT=CLIENT" "%VERIFY_LOG%" >nul || (
  echo [FAIL] notification_outbox did not persist CLIENT subject_type for the invitation flow
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_OUTBOX_SUBJECT_ID=%CLIENT_ID%" "%VERIFY_LOG%" >nul || (
  echo [FAIL] notification_outbox did not persist subject_id=%CLIENT_ID% for the invitation flow
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_OUTBOX_TEMPLATE=" "%VERIFY_LOG%" >nul || (
  echo [FAIL] notification_outbox did not persist template_code for the invitation flow
  type "%VERIFY_LOG%"
  goto :fail
)
findstr /c:"CORE_OUTBOX_DEDUPE=client_invitation:" "%VERIFY_LOG%" >nul || (
  echo [FAIL] notification_outbox did not persist a client_invitation dedupe_key
  type "%VERIFY_LOG%"
  goto :fail
)

echo [12/12] Client users/roles smoke completed.
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
del /q "%REGISTER_FILE%" 2>nul
del /q "%REGISTER_BODY_FILE%" 2>nul
del /q "%VERIFY_FILE%" 2>nul
del /q "%ME_FILE%" 2>nul
del /q "%LOGIN_FILE%" 2>nul
del /q "%LOGIN_BODY_FILE%" 2>nul
del /q "%CORE_VERIFY_FILE%" 2>nul
del /q "%PORTAL_ME_FILE%" 2>nul
del /q "%USERS_FILE%" 2>nul
del /q "%ROLE_BODY_FILE%" 2>nul
del /q "%ROLE_FILE%" 2>nul
del /q "%USERS_AFTER_ROLE_FILE%" 2>nul
del /q "%INVITE_BODY_FILE%" 2>nul
del /q "%INVITE_FILE%" 2>nul
del /q "%INVITATIONS_FILE%" 2>nul
del /q "%RESEND_BODY_FILE%" 2>nul
del /q "%RESEND_FILE%" 2>nul
del /q "%REVOKE_BODY_FILE%" 2>nul
del /q "%REVOKE_FILE%" 2>nul
del /q "%REVOKE_AGAIN_FILE%" 2>nul
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
if "%OUT%"=="" set "OUT=%TEMP%\client_users_resp_%RANDOM%.json"
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
