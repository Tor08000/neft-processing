@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

set "SCRIPT_NAME=seed_partner_money_e2e"

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
if "%AUTH_URL%"=="" set "AUTH_URL=%BASE_URL%/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%BASE_URL%/api/core"
if "%CORE_ADMIN%"=="" set "CORE_ADMIN=%CORE_BASE%/v1/admin"
if "%CORE_ADMIN_VERIFY%"=="" set "CORE_ADMIN_VERIFY=%CORE_BASE%/admin/auth/verify"
if "%CORE_ADMIN_FINANCE_URL%"=="" set "CORE_ADMIN_FINANCE_URL=%CORE_ADMIN%/finance"
if "%CORE_PARTNER%"=="" set "CORE_PARTNER=%CORE_BASE%/partner"
if "%CORE_PORTAL%"=="" set "CORE_PORTAL=%CORE_BASE%/portal"

call :normalize_url AUTH_URL
call :normalize_url CORE_BASE
call :normalize_url CORE_ADMIN
call :normalize_url CORE_ADMIN_VERIFY
call :normalize_url CORE_ADMIN_FINANCE_URL
call :normalize_url CORE_PARTNER
call :normalize_url CORE_PORTAL

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=partner@neft.local"
if "%PARTNER_PASSWORD%"=="" set "PARTNER_PASSWORD=Partner123!"
if "%PARTNER_ORG_NAME%"=="" set "PARTNER_ORG_NAME=demo-partner"
if "%PARTNER_INN%"=="" set "PARTNER_INN=7700000000"
if "%PARTNER_LEGAL_STATUS%"=="" set "PARTNER_LEGAL_STATUS=VERIFIED"
if "%PARTNER_LEDGER_AMOUNT%"=="" set "PARTNER_LEDGER_AMOUNT=12000"
if "%PARTNER_PAYOUT_THRESHOLD%"=="" set "PARTNER_PAYOUT_THRESHOLD=1000"

set "ADMIN_LOGIN_FILE=%TEMP%\seed_partner_money_admin_login_%RANDOM%.json"
set "PARTNER_LOGIN_FILE=%TEMP%\seed_partner_money_partner_login_%RANDOM%.json"
set "SEED_FILE=%TEMP%\seed_partner_money_seed_%RANDOM%.json"

set "ADMIN_LOGIN_BODY_FILE=%TEMP%\seed_partner_money_admin_login_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%ADMIN_LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%ADMIN_EMAIL%','password': r'%ADMIN_PASSWORD%','portal':'admin'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%ADMIN_LOGIN_BODY_FILE%" "200" "%ADMIN_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%ADMIN_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "ADMIN_TOKEN=%%t"
if "%ADMIN_TOKEN%"=="" (
  echo [FAIL] admin login missing access_token
  if exist "%ADMIN_LOGIN_FILE%" type "%ADMIN_LOGIN_FILE%"
  goto :fail
)

set "ADMIN_AUTH_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
call :http_request "GET" "%CORE_ADMIN_VERIFY%" "%ADMIN_AUTH_HEADER%" "" "204" "%TEMP%\seed_partner_money_admin_verify.txt" || goto :fail

set "PARTNER_SEED_BODY_FILE=%TEMP%\seed_partner_money_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PARTNER_SEED_BODY_FILE%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','org_name': r'%PARTNER_ORG_NAME%','inn': r'%PARTNER_INN%'}), encoding='utf-8')"
call :http_request "POST" "%CORE_ADMIN%/seed/partner-money" "%ADMIN_AUTH_HEADER%" "%PARTNER_SEED_BODY_FILE%" "200,201" "%SEED_FILE%" || goto :fail

for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%SEED_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('partner_org_id') or '')"`) do set "ORG_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%SEED_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('partner_email') or '')"`) do set "SEEDED_PARTNER_EMAIL=%%t"
if "%ORG_ID%"=="" (
  echo [FAIL] partner-money seed missing org id
  if exist "%SEED_FILE%" type "%SEED_FILE%"
  goto :fail
)
if not "%SEEDED_PARTNER_EMAIL%"=="" set "PARTNER_EMAIL=%SEEDED_PARTNER_EMAIL%"

set "PARTNER_LOGIN_BODY_FILE=%TEMP%\seed_partner_money_partner_login_body_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PARTNER_LOGIN_BODY_FILE%').write_text(json.dumps({'email': r'%PARTNER_EMAIL%','password': r'%PARTNER_PASSWORD%','portal':'partner'}), encoding='utf-8')"
call :http_request "POST" "%AUTH_URL%/login" "" "%PARTNER_LOGIN_BODY_FILE%" "200" "%PARTNER_LOGIN_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_LOGIN_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "PARTNER_TOKEN=%%t"
if "%PARTNER_TOKEN%"=="" (
  echo [FAIL] partner login missing access_token
  if exist "%PARTNER_LOGIN_FILE%" type "%PARTNER_LOGIN_FILE%"
  goto :fail
)

set "PARTNER_AUTH_HEADER=Authorization: Bearer %PARTNER_TOKEN%"
call :http_request "GET" "%CORE_PARTNER%/auth/verify" "%PARTNER_AUTH_HEADER%" "" "204" "%TEMP%\seed_partner_money_partner_verify.txt" || goto :fail

set "PARTNER_PORTAL_FILE=%TEMP%\seed_partner_money_portal_me.json"
call :http_request "GET" "%CORE_PORTAL%/me" "%PARTNER_AUTH_HEADER%" "" "200" "%PARTNER_PORTAL_FILE%" || goto :fail
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_PORTAL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); org=data.get('org') or data.get('partner') or {}; print(org.get('id') or '')"`) do set "ACTOR_ORG_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_PORTAL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); entitlements=data.get('entitlements_snapshot') or {}; print(entitlements.get('org_id') or '')"`) do set "FINANCE_ORG_ID=%%t"
for /f "usebackq tokens=*" %%t in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%PARTNER_PORTAL_FILE%').read_text(encoding='utf-8', errors='ignore') or '{}'); caps={str(item).upper() for item in (data.get('capabilities') or [])}; print('PARTNER_FINANCE_VIEW' in caps)"`) do set "HAS_FINANCE_CAP=%%t"
if /i not "%HAS_FINANCE_CAP%"=="True" (
  echo [FAIL] partner portal/me missing PARTNER_FINANCE_VIEW
  if exist "%PARTNER_PORTAL_FILE%" type "%PARTNER_PORTAL_FILE%"
  goto :fail
)
if "%FINANCE_ORG_ID%"=="" (
  if "%ACTOR_ORG_ID%"=="" (
    set "TARGET_ORG_ID=%ORG_ID%"
  ) else (
    set "TARGET_ORG_ID=%ACTOR_ORG_ID%"
  )
) else (
  set "TARGET_ORG_ID=%FINANCE_ORG_ID%"
)

set "LEGAL_PROFILE_BODY_FILE=%TEMP%\seed_partner_money_legal_profile_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LEGAL_PROFILE_BODY_FILE%').write_text(json.dumps({'legal_type': 'LEGAL_ENTITY','country': 'RU','tax_residency': 'RU','tax_regime': 'OSNO','vat_applicable': True,'vat_rate': 20}), encoding='utf-8')"
call :http_request "PUT" "%CORE_PARTNER%/legal/profile" "%PARTNER_AUTH_HEADER%" "%LEGAL_PROFILE_BODY_FILE%" "200" "%TEMP%\seed_partner_money_legal_profile.json" || goto :fail

set "LEGAL_DETAILS_BODY_FILE=%TEMP%\seed_partner_money_legal_details_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LEGAL_DETAILS_BODY_FILE%').write_text(json.dumps({'legal_name': r'%PARTNER_ORG_NAME%','inn': r'%PARTNER_INN%','kpp': '770101001','ogrn': '1027700132195','bank_account': '40702810900000000001','bank_bic': '044525225','bank_name': 'Demo Bank'}), encoding='utf-8')"
call :http_request "PUT" "%CORE_PARTNER%/legal/details" "%PARTNER_AUTH_HEADER%" "%LEGAL_DETAILS_BODY_FILE%" "200" "%TEMP%\seed_partner_money_legal_details.json" || goto :fail

set "LEGAL_STATUS_BODY_FILE=%TEMP%\seed_partner_money_legal_status_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LEGAL_STATUS_BODY_FILE%').write_text(json.dumps({'status': r'%PARTNER_LEGAL_STATUS%','comment': 'Seeded by seed_partner_money_e2e'}), encoding='utf-8')"
call :http_request "POST" "%CORE_ADMIN%/partners/%TARGET_ORG_ID%/legal-profile/status" "%ADMIN_AUTH_HEADER%" "%LEGAL_STATUS_BODY_FILE%" "200" "%TEMP%\seed_partner_money_legal_status.json" || goto :fail

set "PAYOUT_POLICY_BODY_FILE=%TEMP%\seed_partner_money_policy_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%PAYOUT_POLICY_BODY_FILE%').write_text(json.dumps({'currency': 'RUB','min_payout_amount': %PARTNER_PAYOUT_THRESHOLD%,'payout_hold_days': 0,'payout_schedule': 'WEEKLY'}), encoding='utf-8')"
call :http_request "POST" "%CORE_ADMIN_FINANCE_URL%/partners/%TARGET_ORG_ID%/payout-policy" "%ADMIN_AUTH_HEADER%" "%PAYOUT_POLICY_BODY_FILE%" "200" "%TEMP%\seed_partner_money_policy.json" || goto :fail

set "LEDGER_BODY_FILE=%TEMP%\seed_partner_money_ledger_%RANDOM%.json"
python -c "import json; from pathlib import Path; Path(r'%LEDGER_BODY_FILE%').write_text(json.dumps({'amount': %PARTNER_LEDGER_AMOUNT%,'currency': 'RUB','entry_type': 'EARNED','direction': 'CREDIT','description': 'Seeded earning'}), encoding='utf-8')"
call :http_request "POST" "%CORE_ADMIN_FINANCE_URL%/partners/%TARGET_ORG_ID%/ledger/seed" "%ADMIN_AUTH_HEADER%" "%LEDGER_BODY_FILE%" "200,201" "%TEMP%\seed_partner_money_ledger.json" || goto :fail

call :http_request "GET" "%CORE_PARTNER%/finance/dashboard" "%PARTNER_AUTH_HEADER%" "" "200" "%TEMP%\seed_partner_money_dashboard.json" || goto :fail

echo [PASS] partner_org_id=%TARGET_ORG_ID%
echo [PASS] partner_email=%PARTNER_EMAIL%
echo [PASS] partner finance dashboard ready
exit /b 0

:http_request
set "METHOD=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "BODY_FILE=%~4"
set "EXPECTED=%~5"
set "OUT=%~6"
set "CODE="
if "%OUT%"=="" set "OUT=%TEMP%\%SCRIPT_NAME%_resp_%RANDOM%.json"
if exist "%OUT%" del /q "%OUT%" 2>nul
if "%BODY_FILE%"=="" (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
) else (
  if "%HEADER%"=="" (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  ) else (
    for /f "usebackq tokens=*" %%c in (`curl.exe -s -S -o "%OUT%" -w "%%{http_code}" -X %METHOD% -H "%HEADER%" -H "Content-Type: application/json" --data-binary "@%BODY_FILE%" "%URL%" 2^>nul`) do set "CODE=%%c"
  )
)
if "%CODE%"=="" exit /b 1
set "EXPECTED_LIST=%EXPECTED:,= %"
set "MATCHED="
for %%e in (%EXPECTED_LIST%) do (
  if "%%e"=="%CODE%" set "MATCHED=1"
)
if not defined MATCHED (
  for %%e in (%EXPECTED_LIST%) do (
    if "%%e"=="200" (
      if exist "%OUT%" (
        findstr /C:"access_token" "%OUT%" >nul && set "MATCHED=1"
      )
    )
  )
)
if defined MATCHED exit /b 0
echo [FAIL] %METHOD% %URL% expected %EXPECTED% got %CODE%
if exist "%OUT%" type "%OUT%"
exit /b 1

:normalize_url
set "URL_VAR=%~1"
call set "URL_VALUE=%%%URL_VAR%%%"
if "%URL_VALUE%"=="" exit /b 0
if /i "%URL_VALUE:~0,4%"=="http" exit /b 0
if "%URL_VALUE:~0,1%"=="/" (
  call set "%URL_VAR%=%BASE_URL%%URL_VALUE%"
)
exit /b 0

:fail
echo [FAIL] %SCRIPT_NAME% failed.
exit /b 1
