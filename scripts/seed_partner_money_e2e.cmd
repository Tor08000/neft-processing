@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=seed_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%CORE_BASE%/admin"
if "%CORE_ADMIN_FINANCE_URL%"=="" set "CORE_ADMIN_FINANCE_URL=%CORE_ADMIN_URL%/finance"
if "%CORE_ADMIN_SETTLEMENT_URL%"=="" set "CORE_ADMIN_SETTLEMENT_URL=%CORE_ADMIN_URL%/settlement"
if "%CORE_PARTNER_URL%"=="" set "CORE_PARTNER_URL=%CORE_BASE%/partner"
if "%CORE_PORTAL_URL%"=="" set "CORE_PORTAL_URL=%CORE_BASE%/portal"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=partner"
if "%PARTNER_LEGAL_STATUS%"=="" set "PARTNER_LEGAL_STATUS=VERIFIED"
if "%PARTNER_LEDGER_AMOUNT%"=="" set "PARTNER_LEDGER_AMOUNT=12000"
if "%PARTNER_PAYOUT_THRESHOLD%"=="" set "PARTNER_PAYOUT_THRESHOLD=1000"

call :login "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "admin" ADMIN_TOKEN || goto :fail
call :login "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" "partner" PARTNER_TOKEN || goto :fail

set "ADMIN_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
set "PARTNER_HEADER=Authorization: Bearer %PARTNER_TOKEN%"

call :http_get "%CORE_PORTAL_URL%/me" "%PARTNER_HEADER%" "%TEMP%\partner_portal_me.json" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\partner_portal_me.json')).get('org',{}).get('id',''))"`) do set "ORG_ID=%%t"
if "%ORG_ID%"=="" (
  echo [FAIL] No partner org id returned.
  exit /b 1
)

set "LEGAL_PROFILE_BODY={\"legal_type\":\"LEGAL_ENTITY\",\"country\":\"RU\",\"tax_residency\":\"RU\",\"tax_regime\":\"OSNO\",\"vat_applicable\":true,\"vat_rate\":20}"
call :http_put "%CORE_PARTNER_URL%/legal/profile" "%PARTNER_HEADER%" "%LEGAL_PROFILE_BODY%" "200" || goto :fail

set "LEGAL_DETAILS_BODY={\"legal_name\":\"Demo Partner LLC\",\"inn\":\"7701234567\",\"kpp\":\"770101001\",\"ogrn\":\"1027700132195\",\"bank_account\":\"40702810900000000001\",\"bank_bic\":\"044525225\",\"bank_name\":\"Demo Bank\"}"
call :http_put "%CORE_PARTNER_URL%/legal/details" "%PARTNER_HEADER%" "%LEGAL_DETAILS_BODY%" "200" || goto :fail

set "LEGAL_STATUS_BODY={\"status\":\"%PARTNER_LEGAL_STATUS%\",\"comment\":\"Seeded by %SCRIPT_NAME%\"}"
call :http_post "%CORE_ADMIN_URL%/partners/%ORG_ID%/legal-profile/status" "%ADMIN_HEADER%" "%LEGAL_STATUS_BODY%" "200" || goto :fail

set "PAYOUT_POLICY_BODY={\"currency\":\"RUB\",\"min_payout_amount\":%PARTNER_PAYOUT_THRESHOLD%,\"payout_hold_days\":0,\"payout_schedule\":\"WEEKLY\"}"
call :http_post "%CORE_ADMIN_FINANCE_URL%/partners/%ORG_ID%/payout-policy" "%ADMIN_HEADER%" "%PAYOUT_POLICY_BODY%" "200" || goto :fail

set "LEDGER_BODY={\"amount\":%PARTNER_LEDGER_AMOUNT%,\"currency\":\"RUB\",\"entry_type\":\"EARNED\",\"direction\":\"CREDIT\",\"description\":\"Seeded earning\"}"
call :http_post "%CORE_ADMIN_FINANCE_URL%/partners/%ORG_ID%/ledger/seed" "%ADMIN_HEADER%" "%LEDGER_BODY%" "201" || goto :fail

for /f "usebackq tokens=*" %%t in (`python -c "from datetime import datetime, timedelta, timezone; dt=datetime.now(timezone.utc); start=(dt - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0); print(start.isoformat())"`) do set "SETTLE_START=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())"`) do set "SETTLE_END=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import uuid; print(uuid.uuid4())"`) do set "SETTLE_KEY=%%t"
set "SETTLEMENT_BODY={\"partner_id\":\"%ORG_ID%\",\"currency\":\"RUB\",\"period_start\":\"%SETTLE_START%\",\"period_end\":\"%SETTLE_END%\",\"idempotency_key\":\"seed-%SETTLE_KEY%\"}"
call :http_post "%CORE_ADMIN_SETTLEMENT_URL%/periods/calculate" "%ADMIN_HEADER%" "%SETTLEMENT_BODY%" "200" || goto :fail

echo [SEED] %SCRIPT_NAME% completed.
exit /b 0

:login
set "EMAIL=%~1"
set "PASSWORD=%~2"
set "PORTAL=%~3"
set "TOKEN_VAR=%~4"
set "TOKEN="
curl -s -S -X POST "%AUTH_URL%/login" -H "Content-Type: application/json" -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\",\"portal\":\"%PORTAL%\"}" > "%TEMP%\\%SCRIPT_NAME%_login.json"
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open(r'%TEMP%\\%SCRIPT_NAME%_login.json')).get('access_token',''))"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned for %EMAIL% portal %PORTAL%.
  exit /b 1
)
set "%TOKEN_VAR%=%TOKEN%"
exit /b 0

:http_get
set "URL=%~1"
set "HEADER=%~2"
set "OUT=%~3"
if "%HEADER%"=="" (
  curl -s -S "%URL%" > "%OUT%"
) else (
  curl -s -S -H "%HEADER%" "%URL%" > "%OUT%"
)
exit /b 0

:http_post
set "URL=%~1"
set "HEADER=%~2"
set "BODY=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" exit /b 0
echo [FAIL] POST %URL% expected %EXPECTED% got %CODE%
exit /b 1

:http_put
set "URL=%~1"
set "HEADER=%~2"
set "BODY=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X PUT "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" exit /b 0
echo [FAIL] PUT %URL% expected %EXPECTED% got %CODE%
exit /b 1

:fail
echo [SEED] %SCRIPT_NAME% failed.
exit /b 1
