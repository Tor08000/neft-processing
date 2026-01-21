@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_ADMIN_URL=%GATEWAY_BASE%%CORE_BASE%/api/v1/admin"
set "CORE_CLIENT_URL=%GATEWAY_BASE%%CORE_BASE%/client/api/v1"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin"
if "%CLIENT_EMAIL%"=="" set "CLIENT_EMAIL=client@neft.local"
if "%CLIENT_PASSWORD%"=="" set "CLIENT_PASSWORD=client"

set "ADMIN_TOKEN="
set "CLIENT_TOKEN="

call :login "%ADMIN_EMAIL%" "%ADMIN_PASSWORD%" ADMIN_TOKEN || goto :fail
call :login "%CLIENT_EMAIL%" "%CLIENT_PASSWORD%" CLIENT_TOKEN || goto :fail

set "ADMIN_HEADER=Authorization: Bearer %ADMIN_TOKEN%"
set "CLIENT_HEADER=Authorization: Bearer %CLIENT_TOKEN%"

call :post_step "Seed billing data" "%CORE_ADMIN_URL%/billing/seed" "" "%ADMIN_HEADER%" "200" "" || goto :fail

set "SUPPORT_BODY={\"scope_type\":\"CLIENT\",\"subject_type\":\"OTHER\",\"title\":\"E2E seed ticket\",\"description\":\"Seeded by scripts/seed_e2e.cmd\"}"
call :post_step "Create support request" "%CORE_CLIENT_URL%/support/requests" "%SUPPORT_BODY%" "%CLIENT_HEADER%" "200" "201" || goto :fail

echo [SEED] E2E seed completed.
exit /b 0

:login
set "EMAIL=%~1"
set "PASSWORD=%~2"
set "TOKEN_VAR=%~3"
set "TOKEN="

curl -s -S -X POST "%AUTH_URL%/login" -H "Content-Type: application/json" -d "{\"email\":\"%EMAIL%\",\"password\":\"%PASSWORD%\"}" > login.json
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

:fail
echo [SEED] Failed.
exit /b 1
