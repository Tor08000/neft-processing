@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%BASE_URL%"=="" set "BASE_URL=http://localhost"
set "CLIENT_EMAIL=client@neft.local"
set "CLIENT_PASSWORD=Neft123!"
set "PARTNER_EMAIL=partner@neft.local"
set "PARTNER_PASSWORD=Partner123!"
set "CREATED_ID="
set "PARTNER_ID="
set "CLIENT_ACCESS_STATE="

echo [INFO] Base URL: %BASE_URL%

call :step "gateway health" "curl -sS -f %BASE_URL%/health" || exit /b 1
call :step "auth health" "curl -sS -f %BASE_URL%/api/auth/health" || exit /b 1
call :step "core health" "curl -sS -f %BASE_URL%/api/core/health" || exit /b 1

call :login "%CLIENT_EMAIL%" "%CLIENT_PASSWORD%" CLIENT_TOKEN || exit /b 1
if not defined CLIENT_TOKEN (
  echo [FAIL] client token is empty after login
  exit /b 1
)

call :portal_me "%CLIENT_TOKEN%" CLIENT_ACCESS_STATE || exit /b 1
if /I "%CLIENT_ACCESS_STATE%"=="NEEDS_ONBOARDING" (
  call :step "onboarding create profile" "curl -sS -f -H \"Content-Type: application/json\" -H \"Authorization: Bearer %CLIENT_TOKEN%\" -d \"{\"name\":\"Demo Client\",\"inn\":\"7707083893\",\"client_type\":\"LEGAL\"}\" %BASE_URL%/api/core/client/onboarding/profile" || exit /b 1
  call :portal_me "%CLIENT_TOKEN%" CLIENT_ACCESS_STATE || exit /b 1
)

if not /I "%CLIENT_ACCESS_STATE%"=="ACTIVE" (
  echo [FAIL] portal/me expected ACTIVE, got "%CLIENT_ACCESS_STATE%"
  exit /b 1
)
echo [PASS] portal/me is ACTIVE

call :demo_partner "%CLIENT_TOKEN%" PARTNER_ID || exit /b 1
if not defined PARTNER_ID (
  echo [FAIL] demo partner id not found
  exit /b 1
)

call :create_request "%CLIENT_TOKEN%" "%PARTNER_ID%" CREATED_ID || exit /b 1
if not defined CREATED_ID (
  echo [FAIL] created request id is empty
  exit /b 1
)

call :login "%PARTNER_EMAIL%" "%PARTNER_PASSWORD%" PARTNER_TOKEN || exit /b 1
if not defined PARTNER_TOKEN (
  echo [FAIL] partner token is empty after login
  exit /b 1
)

call :partner_has_request "%PARTNER_TOKEN%" "%CREATED_ID%" || exit /b 1
call :partner_action "%PARTNER_TOKEN%" "%CREATED_ID%" accept || exit /b 1
call :partner_action "%PARTNER_TOKEN%" "%CREATED_ID%" start || exit /b 1
call :partner_action "%PARTNER_TOKEN%" "%CREATED_ID%" complete || exit /b 1
call :client_assert_done "%CLIENT_TOKEN%" "%CREATED_ID%" || exit /b 1

echo SELFTEST RESULT: PASS
exit /b 0

:step
set "STEP_NAME=%~1"
set "CMD=%~2"
for /f "delims=" %%A in ('%CMD% 2^>^&1') do set "OUT=%%A"
if errorlevel 1 (
  echo [FAIL] %STEP_NAME%
  exit /b 1
)
echo [PASS] %STEP_NAME%
exit /b 0

:login
set "EMAIL=%~1"
set "PASSWORD=%~2"
set "OUTVAR=%~3"
set "RESP=%TEMP%\selftest_login_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_login_%RANDOM%.txt"
echo [INFO] login endpoint: %BASE_URL%/api/auth/login email=%EMAIL%
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Content-Type: application/json" -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\"}" "%BASE_URL%/api/auth/login" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="200" (
  echo [FAIL] login %EMAIL% (status %CODE%)
  type "%RESP%"
  exit /b 1
)
for /f "usebackq delims=" %%T in (`python -c "import json;from pathlib import Path;d=json.loads(Path(r'%RESP%').read_text(encoding='utf-8',errors='ignore') or '{}');print(d.get('access_token',''))"`) do set "TOKEN=%%T"
if "%TOKEN%"=="" (
  echo [FAIL] login %EMAIL% token missing
  type "%RESP%"
  exit /b 1
)
set "%OUTVAR%=%TOKEN%"
echo [PASS] login %EMAIL%
exit /b 0

:portal_me
set "TOKEN=%~1"
set "OUTVAR=%~2"
set "RESP=%TEMP%\selftest_me_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_me_%RANDOM%.txt"
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%BASE_URL%/api/core/portal/me" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="200" (
  echo [FAIL] portal/me (status %CODE%)
  type "%RESP%"
  exit /b 1
)
for /f "usebackq delims=" %%A in (`python -c "import json;from pathlib import Path;d=json.loads(Path(r'%RESP%').read_text(encoding='utf-8',errors='ignore') or '{}');print(d.get('access_state',''))"`) do set "STATE=%%A"
set "%OUTVAR%=%STATE%"
echo [PASS] portal/me access_state=%STATE%
exit /b 0

:demo_partner
set "TOKEN=%~1"
set "OUTVAR=%~2"
set "RESP=%TEMP%\selftest_partner_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_partner_%RANDOM%.txt"
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%BASE_URL%/api/core/partners/demo" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="200" (
  echo [FAIL] get demo partner (status %CODE%)
  type "%RESP%"
  exit /b 1
)
for /f "usebackq delims=" %%A in (`python -c "import json;from pathlib import Path;d=json.loads(Path(r'%RESP%').read_text(encoding='utf-8',errors='ignore') or '{}');print(d.get('partner_id',''))"`) do set "PID=%%A"
set "%OUTVAR%=%PID%"
echo [PASS] demo partner id resolved
exit /b 0

:create_request
set "TOKEN=%~1"
set "PARTNER_ID=%~2"
set "OUTVAR=%~3"
set "RESP=%TEMP%\selftest_create_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_create_%RANDOM%.txt"
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Content-Type: application/json" -H "Authorization: Bearer %TOKEN%" -d "{\"partner_id\":\"%PARTNER_ID%\",\"service_id\":\"cccccccc-cccc-cccc-cccc-cccccccccccc\",\"payload\":{\"demo\":true}}" "%BASE_URL%/api/core/services/requests" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="201" (
  echo [FAIL] create service request (status %CODE%)
  type "%RESP%"
  exit /b 1
)
for /f "usebackq delims=" %%A in (`python -c "import json;from pathlib import Path;d=json.loads(Path(r'%RESP%').read_text(encoding='utf-8',errors='ignore') or '{}');print(d.get('id',''))"`) do set "RID=%%A"
set "%OUTVAR%=%RID%"
echo [PASS] create service request %RID%
exit /b 0

:partner_has_request
set "TOKEN=%~1"
set "RID=%~2"
set "RESP=%TEMP%\selftest_list_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_list_%RANDOM%.txt"
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%BASE_URL%/api/core/partner/services/requests" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="200" (
  echo [FAIL] partner list service requests (status %CODE%)
  type "%RESP%"
  exit /b 1
)
python -c "import json,sys;from pathlib import Path;rid=r'%RID%';items=json.loads(Path(r'%RESP%').read_text(encoding='utf-8',errors='ignore') or '[]');sys.exit(0 if any(i.get('id')==rid for i in items) else 1)"
if errorlevel 1 (
  echo [FAIL] partner does not see request %RID%
  exit /b 1
)
echo [PASS] partner sees request %RID%
exit /b 0

:partner_action
set "TOKEN=%~1"
set "RID=%~2"
set "ACTION=%~3"
set "RESP=%TEMP%\selftest_action_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_action_%RANDOM%.txt"
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" -X POST "%BASE_URL%/api/core/partner/services/requests/%RID%/%ACTION%" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="200" (
  echo [FAIL] partner action %ACTION% (status %CODE%)
  type "%RESP%"
  exit /b 1
)
echo [PASS] partner action %ACTION%
exit /b 0

:client_assert_done
set "TOKEN=%~1"
set "RID=%~2"
set "RESP=%TEMP%\selftest_final_%RANDOM%.json"
set "STATUS=%TEMP%\selftest_final_%RANDOM%.txt"
curl -sS -o "%RESP%" -w "%%{http_code}" -H "Authorization: Bearer %TOKEN%" "%BASE_URL%/api/core/services/requests/%RID%" > "%STATUS%"
set /p CODE=<"%STATUS%"
if not "%CODE%"=="200" (
  echo [FAIL] client fetch final request (status %CODE%)
  type "%RESP%"
  exit /b 1
)
for /f "usebackq delims=" %%A in (`python -c "import json;from pathlib import Path;d=json.loads(Path(r'%RESP%').read_text(encoding='utf-8',errors='ignore') or '{}');print(d.get('status',''))"`) do set "FINAL_STATUS=%%A"
if /I not "%FINAL_STATUS%"=="done" (
  echo [FAIL] final status expected done, got %FINAL_STATUS%
  exit /b 1
)
echo [PASS] client sees final status done
exit /b 0
