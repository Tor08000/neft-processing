@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"

set "SMOKE_EMAIL=client_active_%RANDOM%@example.com"
set "SMOKE_PASSWORD=ClientActive123!"
set "OTP_CODE=0000"

set "TMP_DIR=%TEMP%"

call :http_post "signup" "%GATEWAY_BASE%%AUTH_BASE%/signup" "{\"email\":\"%SMOKE_EMAIL%\",\"password\":\"%SMOKE_PASSWORD%\",\"full_name\":\"Client Active Smoke\",\"consent_personal_data\":true,\"consent_offer\":true}" "201" "%TMP_DIR%\client_active_signup.json" || exit /b 1

call :http_post "login" "%GATEWAY_BASE%%AUTH_BASE%/login" "{\"email\":\"%SMOKE_EMAIL%\",\"password\":\"%SMOKE_PASSWORD%\",\"portal\":\"client\"}" "200" "%TMP_DIR%\client_active_login.json" || exit /b 1

for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_login.json').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('access_token',''))"`) do set "CLIENT_TOKEN=%%T"
if "%CLIENT_TOKEN%"=="" (
  echo [FAIL] login missing access_token
  exit /b 1
)

call :portal_me "NEEDS_ONBOARDING" || exit /b 1

set "ORG_PAYLOAD={\"org_type\":\"LEGAL\",\"name\":\"Smoke Client\",\"inn\":\"7701234567\",\"kpp\":\"770101001\",\"ogrn\":\"1027700132195\",\"address\":\"Москва\"}"
call :http_post "org create" "%GATEWAY_BASE%%CORE_BASE%/client/org" "%ORG_PAYLOAD%" "200" "%TMP_DIR%\client_active_org.json" || exit /b 1

call :portal_me "NEEDS_PLAN" || exit /b 1

call :http_get "plans" "%GATEWAY_BASE%%CORE_BASE%/client/plans" "200" "%TMP_DIR%\client_active_plans.json" || exit /b 1
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_plans.json').read_text(encoding='utf-8', errors='ignore') or '[]'); print((data[0] if data else {}).get('code',''))"`) do set "PLAN_CODE=%%T"
if "%PLAN_CODE%"=="" (
  echo [FAIL] no plans available
  exit /b 1
)

call :http_post "plan select" "%GATEWAY_BASE%%CORE_BASE%/client/subscription/select" "{\"plan_code\":\"%PLAN_CODE%\"}" "200" "%TMP_DIR%\client_active_plan_select.json" || exit /b 1

call :portal_me "NEEDS_CONTRACT" || exit /b 1

call :http_post "contract generate" "%GATEWAY_BASE%%CORE_BASE%/client/contracts/generate" "{}" "200" "%TMP_DIR%\client_active_contract.json" || exit /b 1
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_contract.json').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('contract_id',''))"`) do set "CONTRACT_ID=%%T"
if "%CONTRACT_ID%"=="" (
  echo [FAIL] missing contract_id
  exit /b 1
)

call :http_get "contract get" "%GATEWAY_BASE%%CORE_BASE%/client/contracts/%CONTRACT_ID%" "200" "%TMP_DIR%\client_active_contract_get.json" || exit /b 1

call :http_post "contract sign" "%GATEWAY_BASE%%CORE_BASE%/client/contracts/%CONTRACT_ID%/sign" "{\"otp\":\"%OTP_CODE%\"}" "200" "%TMP_DIR%\client_active_contract_sign.json" || exit /b 1

call :portal_me "ACTIVE" || exit /b 1

set "INVITE_EMAIL=driver_%RANDOM%@example.com"
call :http_post "user invite" "%GATEWAY_BASE%%CORE_BASE%/client/users/invite" "{\"email\":\"%INVITE_EMAIL%\",\"role\":\"CLIENT_DRIVER\"}" "201" "%TMP_DIR%\client_active_user_invite.json" || exit /b 1
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_user_invite.json').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "INVITED_USER_ID=%%T"
if "%INVITED_USER_ID%"=="" (
  echo [FAIL] missing invited user id
  exit /b 1
)

call :http_post "issue card" "%GATEWAY_BASE%%CORE_BASE%/client/cards" "{\"pan_masked\":\"5555 ****\"}" "200" "%TMP_DIR%\client_active_card.json" || exit /b 1
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_card.json').read_text(encoding='utf-8', errors='ignore') or '{}'); print(data.get('id',''))"`) do set "CARD_ID=%%T"
if "%CARD_ID%"=="" (
  echo [FAIL] missing card id
  exit /b 1
)

call :http_post "assign card" "%GATEWAY_BASE%%CORE_BASE%/client/cards/%CARD_ID%/access" "{\"user_id\":\"%INVITED_USER_ID%\",\"scope\":\"VIEW\"}" "200" "%TMP_DIR%\client_active_card_assign.json" || exit /b 1

call :http_get "docs contracts" "%GATEWAY_BASE%%CORE_BASE%/client/docs/contracts" "200" "%TMP_DIR%\client_active_docs.json" || exit /b 1
for /f "usebackq delims=" %%T in (`python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_docs.json').read_text(encoding='utf-8', errors='ignore') or '{}'); items=data.get('items') or []; print(items[0].get('download_url','') if items else '')"`) do set "CONTRACT_DOWNLOAD=%%T"
if "%CONTRACT_DOWNLOAD%"=="" (
  echo [FAIL] no contract document available
  exit /b 1
)

call :http_get "contract download" "%GATEWAY_BASE%%CONTRACT_DOWNLOAD%" "200" "%TMP_DIR%\client_active_contract_pdf.pdf" || exit /b 1

echo [PASS] smoke_client_active_e2e OK
exit /b 0

:portal_me
set "EXPECTED_STATE=%~1"
call :http_get "portal/me" "%GATEWAY_BASE%%CORE_BASE%/portal/me" "200" "%TMP_DIR%\client_active_portal_me.json" || exit /b 1
python -c "import json; from pathlib import Path; data=json.loads(Path(r'%TMP_DIR%\\client_active_portal_me.json').read_text(encoding='utf-8', errors='ignore') or '{}'); state=data.get('access_state'); expected=r'%EXPECTED_STATE%'; print(f'[portal/me] access_state={state} expected={expected}'); raise SystemExit(0 if state==expected else 1)" || exit /b 1
echo [PASS] portal/me %EXPECTED_STATE%
exit /b 0

:http_get
set "LABEL=%~1"
set "URL=%~2"
set "EXPECTED=%~3"
set "OUT_FILE=%~4"
set "STATUS_FILE=%TMP_DIR%\client_active_status_%RANDOM%.txt"
curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "Authorization: Bearer %CLIENT_TOKEN%" "%URL%" > "%STATUS_FILE%"
set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="%EXPECTED%" (
  echo [FAIL] %LABEL% HTTP %STATUS%
  type "%OUT_FILE%"
  exit /b 1
)
echo [PASS] %LABEL%
exit /b 0

:http_post
set "LABEL=%~1"
set "URL=%~2"
set "PAYLOAD=%~3"
set "EXPECTED=%~4"
set "OUT_FILE=%~5"
set "STATUS_FILE=%TMP_DIR%\client_active_status_%RANDOM%.txt"
if "%CLIENT_TOKEN%"=="" (
  curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -X POST "%URL%" -d "%PAYLOAD%" > "%STATUS_FILE%"
) else (
  curl -sS -o "%OUT_FILE%" -w "%%{http_code}" -H "Content-Type: application/json" -H "Authorization: Bearer %CLIENT_TOKEN%" -X POST "%URL%" -d "%PAYLOAD%" > "%STATUS_FILE%"
)
set /p STATUS=<"%STATUS_FILE%"
if not "%STATUS%"=="%EXPECTED%" (
  echo [FAIL] %LABEL% HTTP %STATUS%
  type "%OUT_FILE%"
  exit /b 1
)
echo [PASS] %LABEL%
exit /b 0
