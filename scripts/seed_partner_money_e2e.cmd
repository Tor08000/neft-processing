@echo off
setlocal enabledelayedexpansion

set "SCRIPT_NAME=seed_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_ADMIN_URL%"=="" set "CORE_ADMIN_URL=%CORE_BASE%/v1/admin"
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

set "ADMIN_LOGIN_FILE=%TEMP%\\%SCRIPT_NAME%_admin_login.json"
set "PARTNER_LOGIN_FILE=%TEMP%\\%SCRIPT_NAME%_partner_login.json"
set "ADMIN_TOKEN_FILE=%TEMP%\\%SCRIPT_NAME%_admin_token.txt"
set "PARTNER_TOKEN_FILE=%TEMP%\\%SCRIPT_NAME%_partner_token.txt"

call :login "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" "admin" ADMIN_TOKEN "%ADMIN_LOGIN_FILE%" "%ADMIN_TOKEN_FILE%" || goto :fail
call :login "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" "partner" PARTNER_TOKEN "%PARTNER_LOGIN_FILE%" "%PARTNER_TOKEN_FILE%" || goto :fail

set "ADMIN_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
set "PARTNER_HEADER=Authorization: Bearer %PARTNER_TOKEN%"

for /f "usebackq tokens=*" %%t in (`python -c "import base64, json; from pathlib import Path; token=Path(r'%PARTNER_TOKEN_FILE%').read_text(encoding='utf-8', errors='ignore').strip(); payload=token.split('.')[1] if token and '.' in token else ''; pad='=' * (-len(payload) %% 4); data=json.loads(base64.urlsafe_b64decode(payload + pad) or b'{}'); print(data.get('partner_id') or data.get('org_id') or data.get('user_id') or '')"`) do set "ORG_ID=%%t"
if "%ORG_ID%"=="" (
  echo [FAIL] No partner org id returned.
  exit /b 1
)

set "PARTNER_CREATE_BODY={""id"":""%ORG_ID%"",""name"":""Demo Partner"",""type"":""aggregator"",""status"":""active"",""allowed_ips"":[],""token"":""seed-%ORG_ID%""}"
call :http_post "%CORE_BASE%/api/v1/partners" "" "%PARTNER_CREATE_BODY%" "201" "%TEMP%\\partner_create.json" || goto :fail

set "LEGAL_PROFILE_BODY={""legal_type"":""LEGAL_ENTITY"",""country"":""RU"",""tax_residency"":""RU"",""tax_regime"":""OSNO"",""vat_applicable"":true,""vat_rate"":20}"
call :http_put "%CORE_PARTNER_URL%/legal/profile" "%PARTNER_HEADER%" "%LEGAL_PROFILE_BODY%" "200" "%TEMP%\\partner_legal_profile.json" || goto :fail

set "LEGAL_DETAILS_BODY={""legal_name"":""Demo Partner LLC"",""inn"":""7701234567"",""kpp"":""770101001"",""ogrn"":""1027700132195"",""bank_account"":""40702810900000000001"",""bank_bic"":""044525225"",""bank_name"":""Demo Bank""}"
call :http_put "%CORE_PARTNER_URL%/legal/details" "%PARTNER_HEADER%" "%LEGAL_DETAILS_BODY%" "200" "%TEMP%\\partner_legal_details.json" || goto :fail

set "LEGAL_STATUS_BODY={""status"":""%PARTNER_LEGAL_STATUS%"",""comment"":""Seeded by %SCRIPT_NAME%""}"
call :http_post "%CORE_ADMIN_URL%/partners/%ORG_ID%/legal-profile/status" "%ADMIN_HEADER%" "%LEGAL_STATUS_BODY%" "200" "%TEMP%\\partner_legal_status.json" || goto :fail

set "PAYOUT_POLICY_BODY={""currency"":""RUB"",""min_payout_amount"":%PARTNER_PAYOUT_THRESHOLD%,""payout_hold_days"":0,""payout_schedule"":""WEEKLY""}"
call :http_post "%CORE_ADMIN_FINANCE_URL%/partners/%ORG_ID%/payout-policy" "%ADMIN_HEADER%" "%PAYOUT_POLICY_BODY%" "200" "%TEMP%\\partner_payout_policy.json" || goto :fail

set "LEDGER_BODY={""amount"":%PARTNER_LEDGER_AMOUNT%,""currency"":""RUB"",""entry_type"":""EARNED"",""direction"":""CREDIT"",""description"":""Seeded earning""}"
call :http_post "%CORE_ADMIN_FINANCE_URL%/partners/%ORG_ID%/ledger/seed" "%ADMIN_HEADER%" "%LEDGER_BODY%" "201" "%TEMP%\\partner_ledger_seed.json" || goto :fail

for /f "usebackq tokens=*" %%t in (`python -c "from datetime import datetime, timedelta, timezone; dt=datetime.now(timezone.utc); start=(dt - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0); print(start.isoformat())"`) do set "SETTLE_START=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())"`) do set "SETTLE_END=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import uuid; print(uuid.uuid4())"`) do set "SETTLE_KEY=%%t"
set "SETTLEMENT_BODY={""partner_id"":""%ORG_ID%"",""currency"":""RUB"",""period_start"":""%SETTLE_START%"",""period_end"":""%SETTLE_END%"",""idempotency_key"":""seed-%SETTLE_KEY%""}"
call :http_post "%CORE_ADMIN_SETTLEMENT_URL%/periods/calculate" "%ADMIN_HEADER%" "%SETTLEMENT_BODY%" "200" "%TEMP%\\partner_settlement.json" || goto :fail

echo [PASS] PARTNER_ORG_ID=%ORG_ID%
echo [PASS] PARTNER_EMAIL=%PARTNER_EMAIL%
exit /b 0

:login
set "EMAIL=%~1"
set "PASSWORD=%~2"
set "PORTAL=%~3"
set "TOKEN_VAR=%~4"
set "LOGIN_FILE=%~5"
set "TOKEN_FILE=%~6"
set "TOKEN="
set "LOGIN_BODY={""email"":""%EMAIL%"",""password"":""%PASSWORD%"",""portal"":""%PORTAL%""}"
call :http_post "%AUTH_URL%/login" "" "%LOGIN_BODY%" "200" "%LOGIN_FILE%" || exit /b 1
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); token=data.get('access_token',''); Path(r'%TOKEN_FILE%').write_text(token); print(token)"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned for %EMAIL% portal %PORTAL%.
  type "%LOGIN_FILE%"
  exit /b 1
)
set "%TOKEN_VAR%=%TOKEN%"
exit /b 0

:http_get
set "URL=%~1"
set "HEADER=%~2"
set "OUT=%~3"
call :http_request "GET" "%URL%" "%HEADER%" "" "200" "%OUT%"
exit /b %ERRORLEVEL%

:http_post
set "URL=%~1"
set "HEADER=%~2"
set "BODY=%~3"
set "EXPECTED=%~4"
set "OUT=%~5"
call :http_request "POST" "%URL%" "%HEADER%" "%BODY%" "%EXPECTED%" "%OUT%"
exit /b %ERRORLEVEL%

:http_put
set "URL=%~1"
set "HEADER=%~2"
set "BODY=%~3"
set "EXPECTED=%~4"
set "OUT=%~5"
call :http_request "PUT" "%URL%" "%HEADER%" "%BODY%" "%EXPECTED%" "%OUT%"
exit /b %ERRORLEVEL%

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\\%SCRIPT_NAME%_resp_%RANDOM%.json"
if "%BODY%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%"`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" -d "%BODY%" "%URL%"`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" -d "%BODY%" "%URL%"`) do set "CODE=%%c"
  )
)
if "%CODE%"=="%EXPECTED%" exit /b 0
echo [FAIL] %METHOD% %URL% expected %EXPECTED% got %CODE%
if exist "%OUT%" type "%OUT%"
exit /b 1

:fail
echo [SEED] %SCRIPT_NAME% failed.
exit /b 1
