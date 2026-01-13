@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"
set "CORE_URL=%BASE_URL%/api/core/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"

set "TOKEN="
set "AUTH_HEADER="
set "LEAD_ID="
set "CLIENT_ID=client-smoke-1"

echo [1/10] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

echo [2/10] Create lead...
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "{\"tenant_id\":1,\"source\":\"inbound\",\"company_name\":\"Smoke LLC\",\"contact_name\":\"QA\",\"email\":\"qa@example.com\"}" -X POST -o lead.json "%CORE_URL%/crm/leads"`) do set "CODE=%%c"
if not "%CODE%"=="200" (
  echo [FAIL] Lead create returned %CODE%.
  goto :fail
)
for /f "usebackq tokens=*" %%i in (`python -c "import json; print(json.load(open('lead.json')).get('id',''))"`) do set "LEAD_ID=%%i"
if "%LEAD_ID%"=="" (
  echo [FAIL] No lead id returned.
  goto :fail
)

call :post_step "[3/10] Qualify lead" "%CORE_URL%/crm/leads/%LEAD_ID%/qualify" "{\"client_id\":\"%CLIENT_ID%\",\"tenant_id\":1,\"country\":\"RU\",\"legal_name\":\"Smoke LLC\"}" "%AUTH_HEADER%" "200" "" || goto :fail

call :post_step "[4/10] Request legal" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/REQUEST_LEGAL" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[5/10] Sign contract" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/SIGN_CONTRACT" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[6/10] Assign subscription" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/ASSIGN_SUBSCRIPTION" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[7/10] Apply limits" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/APPLY_LIMITS_PROFILE" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[8/10] Skip cards" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/SKIP_CARDS" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[9/10] Activate client" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/ACTIVATE_CLIENT" "" "%AUTH_HEADER%" "200" "" || goto :fail
call :post_step "[10/10] Allow first operation" "%CORE_URL%/crm/clients/%CLIENT_ID%/onboarding/actions/ALLOW_FIRST_OPERATION" "" "%AUTH_HEADER%" "200" "" || goto :fail

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
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -X POST "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%"`) do set "CODE=%%c"
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

:fail
echo [SMOKE] Failed.
exit /b 1
