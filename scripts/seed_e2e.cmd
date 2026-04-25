@echo off
setlocal EnableExtensions DisableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_ADMIN_URL=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"
set "CORE_CLIENT_URL=%GATEWAY_BASE%%CORE_BASE%/client/api/v1"
set "CORE_PARTNER_URL=%GATEWAY_BASE%%CORE_BASE%/partner"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=Client123!"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"
if "%PARTNER_LEGAL_STATUS%"=="" set "PARTNER_LEGAL_STATUS=VERIFIED"
if "%PARTNER_LEDGER_AMOUNT%"=="" set "PARTNER_LEDGER_AMOUNT=12000"
if "%PARTNER_PAYOUT_THRESHOLD%"=="" set "PARTNER_PAYOUT_THRESHOLD=1000"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="
set "PARTNER_TOKEN="

call :login "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "admin" ADMIN_TOKEN || goto :fail
call :login "%CLIENT_EMAIL%" "%CLIENT_PASSWORD%" "client" CLIENT_TOKEN || goto :fail
call :login "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" "partner" PARTNER_TOKEN || goto :fail

set "ADMIN_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
set "CLIENT_HEADER=Authorization: Bearer %CLIENT_TOKEN%"
set "PARTNER_HEADER=Authorization: Bearer %PARTNER_TOKEN%"

call :post_step "Seed billing data" "%CORE_ADMIN_URL%/billing/seed" "" "%ADMIN_HEADER%" "200" "" || goto :fail

set "SUPPORT_BODY={\"scope_type\":\"CLIENT\",\"subject_type\":\"OTHER\",\"title\":\"E2E seed ticket\",\"description\":\"Seeded by scripts/seed_e2e.cmd\"}"
call :post_step "Create support request" "%CORE_CLIENT_URL%/support/requests" "%SUPPORT_BODY%" "%CLIENT_HEADER%" "200" "201" || goto :fail

curl -s -S -H "%PARTNER_HEADER%" "%CORE_PARTNER_URL%/me" > partner_me.json
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open('partner_me.json')).get('org',{}).get('id',''))"`) do set "ORG_ID=%%t"
if "%ORG_ID%"=="" (
  echo [FAIL] No partner org id returned.
  exit /b 1
)

set "LEGAL_PROFILE_BODY={\"legal_type\":\"LEGAL_ENTITY\",\"country\":\"RU\",\"tax_residency\":\"RU\",\"tax_regime\":\"OSNO\",\"vat_applicable\":true,\"vat_rate\":20}"
call :put_step "Seed partner legal profile" "%CORE_PARTNER_URL%/legal/profile" "%LEGAL_PROFILE_BODY%" "%PARTNER_HEADER%" "200" "" || goto :fail

set "LEGAL_DETAILS_BODY={\"legal_name\":\"Demo Partner LLC\",\"inn\":\"7701234567\",\"kpp\":\"770101001\",\"ogrn\":\"1027700132195\",\"bank_account\":\"40702810900000000001\",\"bank_bic\":\"044525225\",\"bank_name\":\"Demo Bank\"}"
call :put_step "Seed partner legal details" "%CORE_PARTNER_URL%/legal/details" "%LEGAL_DETAILS_BODY%" "%PARTNER_HEADER%" "200" "" || goto :fail

set "LEGAL_STATUS_BODY={\"status\":\"%PARTNER_LEGAL_STATUS%\",\"comment\":\"Seeded by scripts/seed_e2e.cmd\"}"
call :post_step "Set partner legal status" "%CORE_ADMIN_URL%/partners/%ORG_ID%/legal-profile/status" "%LEGAL_STATUS_BODY%" "%ADMIN_HEADER%" "200" "" || goto :fail

set "PAYOUT_POLICY_BODY={\"currency\":\"RUB\",\"min_payout_amount\":%PARTNER_PAYOUT_THRESHOLD%,\"payout_hold_days\":0,\"payout_schedule\":\"WEEKLY\"}"
call :post_step "Seed partner payout policy" "%CORE_ADMIN_URL%/finance/partners/%ORG_ID%/payout-policy" "%PAYOUT_POLICY_BODY%" "%ADMIN_HEADER%" "200" "" || goto :fail

set "LEDGER_BODY={\"amount\":%PARTNER_LEDGER_AMOUNT%,\"currency\":\"RUB\",\"entry_type\":\"EARNED\",\"direction\":\"CREDIT\",\"description\":\"Seeded earning\"}"
call :post_step "Seed partner ledger entry" "%CORE_ADMIN_URL%/finance/partners/%ORG_ID%/ledger/seed" "%LEDGER_BODY%" "%ADMIN_HEADER%" "201" "" || goto :fail

echo [SEED] E2E seed completed.
exit /b 0

:login
set "EMAIL=%~1"
set "PASSWORD=%~2"
set "PORTAL=%~3"
set "TOKEN_VAR=%~4"
set "TOKEN="

curl -s -S -X POST "%AUTH_URL%/login" -H "Content-Type: application/json" -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"portal\":\"%PORTAL%\"}" > login.json
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open('login.json')).get('access_token',''))"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned for %EMAIL%.
  exit /b 1
)
set "%TOKEN_VAR%=%TOKEN%"
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

:put_step
set "LABEL=%~1"
set "URL=%~2"
set "BODY=%~3"
set "HEADER=%~4"
set "EXPECTED=%~5"
set "ALT=%~6"
set "CODE="
if "%BODY%"=="" (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -X PUT "%URL%"`) do set "CODE=%%c"
) else (
  for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X PUT "%URL%"`) do set "CODE=%%c"
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
echo [SEED] Failed.
exit /b 1
