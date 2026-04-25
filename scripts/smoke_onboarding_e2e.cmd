@echo off
setlocal enabledelayedexpansion

if "%AUTH_HOST_BASE%"=="" set "AUTH_HOST_BASE=http://localhost:8002"
if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
set "CORE_URL=%CORE_API_BASE%/api/v1/admin"
if "%CRM_VERSION%"=="" set "CRM_VERSION=1"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"

set "TOKEN="
set "AUTH_HEADER="
set "LEAD_ID="
set "CRM_VERSION_HEADER=X-CRM-Version: %CRM_VERSION%"
set "RUN_ID="
set "CLIENT_ID="
set "LEAD_EMAIL="
set "COMPANY_NAME="
set "LEAD_BODY_FILE=%TEMP%\onboarding_lead_%RANDOM%.json"
set "QUALIFY_BODY_FILE=%TEMP%\onboarding_qualify_%RANDOM%.json"

call :wait_for_status "%CORE_API_BASE%/health" "200" 20 2 || goto :fail

for /f "usebackq delims=" %%R in (`python -c "import uuid; print(uuid.uuid4().hex[:8])"`) do set "RUN_ID=%%R"
if "%RUN_ID%"=="" (
  echo [FAIL] Could not generate run id.
  goto :fail
)
set "CLIENT_ID=client-smoke-%RUN_ID%"
set "LEAD_EMAIL=qa+%RUN_ID%@example.com"
set "COMPANY_NAME=Smoke LLC %RUN_ID%"

echo [1/10] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

echo [2/10] Create lead...
del /q lead.json 2>nul
python -c "import json; from pathlib import Path; Path(r'%LEAD_BODY_FILE%').write_text(json.dumps({'tenant_id': 1, 'source': 'inbound', 'company_name': r'%COMPANY_NAME%', 'contact_name': 'QA', 'email': r'%LEAD_EMAIL%'}), encoding='utf-8')"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "%CRM_VERSION_HEADER%" -H "Content-Type: application/json" --data-binary "@%LEAD_BODY_FILE%" -X POST -o lead.json "%CORE_URL%/crm/leads"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Lead create returned %CODE%.
  if exist lead.json type lead.json
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; print(json.load(open('lead.json')).get('id',''))"`) do set "LEAD_ID=%%i"
if "%LEAD_ID%"=="" (
  echo [FAIL] No lead id returned.
  goto :fail
)

python -c "import json; from pathlib import Path; Path(r'%QUALIFY_BODY_FILE%').write_text(json.dumps({'client_id': r'%CLIENT_ID%', 'tenant_id': 1, 'country': 'RU', 'legal_name': r'%COMPANY_NAME%'}), encoding='utf-8')"
call :post_step_file "[3/11] Qualify lead" "%CORE_URL%/crm/leads/%LEAD_ID%/qualify" "%QUALIFY_BODY_FILE%" "%AUTH_HEADER%" "200" "" || goto :fail

call :post_step "[4/11] Request legal" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/REQUEST_LEGAL" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[5/11] Sign contract" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/SIGN_CONTRACT" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[6/11] Assign subscription" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/ASSIGN_SUBSCRIPTION" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[7/11] Apply limits" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/APPLY_LIMITS_PROFILE" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[8/11] Skip cards" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/SKIP_CARDS" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[9/11] Activate client" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/ACTIVATE_CLIENT" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[10/11] Allow first operation" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/ALLOW_FIRST_OPERATION" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :verify_state "[11/11] Verify onboarding state" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding" "%AUTH_HEADER%" "FIRST_OPERATION_ALLOWED" || goto :fail

del /q "%LEAD_BODY_FILE%" 2>nul
del /q "%QUALIFY_BODY_FILE%" 2>nul
echo [SMOKE] Onboarding flow completed.
exit /b 0

:post_step
set "LABEL=%~1"
set "URL=%~2"
set "BODY=%~3"
set "HEADER=%~4"
set "EXPECTED=%~5"
set "ALT=%~6"
set "CODE="
if "%BODY%"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "%CRM_VERSION_HEADER%" -X POST "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "%CRM_VERSION_HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%"`) do set "CODE=%%c"
)
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
if not "%ALT%"=="" if "%CODE%"=="%ALT%" (
  echo [OK] %LABEL% (%CODE%)
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:post_step_file
set "LABEL=%~1"
set "URL=%~2"
set "BODY_FILE=%~3"
set "HEADER=%~4"
set "EXPECTED=%~5"
set "ALT=%~6"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "%CRM_VERSION_HEADER%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" -X POST "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
if not "%ALT%"=="" if "%CODE%"=="%ALT%" (
  echo [OK] %LABEL% (%CODE%)
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:verify_state
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "EXPECTED_STATE=%~4"
del /q onboarding_status.json 2>nul
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%HEADER%" -H "%CRM_VERSION_HEADER%" -o onboarding_status.json "%URL%"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] %LABEL% expected 200 got %CODE%
  if exist onboarding_status.json type onboarding_status.json
  exit /b 1
)
set "ACTUAL_STATE="
for /f "usebackq delims=" %%s in (`python -c "import json; print(json.load(open('onboarding_status.json')).get('state',''))"`) do set "ACTUAL_STATE=%%s"
if /I "%ACTUAL_STATE%"=="%EXPECTED_STATE%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected state %EXPECTED_STATE% got %ACTUAL_STATE%
if exist onboarding_status.json type onboarding_status.json
exit /b 1

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

:fail
del /q "%LEAD_BODY_FILE%" 2>nul
del /q "%QUALIFY_BODY_FILE%" 2>nul
echo [SMOKE] Failed.
exit /b 1
