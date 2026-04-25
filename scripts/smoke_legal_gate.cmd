@echo off
setlocal enabledelayedexpansion

if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=http://localhost"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_ROOT=%GATEWAY_BASE%%CORE_BASE%"
set "ADMIN_URL=%CORE_ROOT%/api/v1/admin"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"

set "TOKEN="
set "AUTH_HEADER="

echo [1/6] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

set "CREATE_BODY={\"code\":\"LEGAL_SMOKE\",\"version\":\"1\",\"title\":\"Legal Smoke\",\"locale\":\"ru\",\"effective_from\":\"2025-01-01T00:00:00Z\",\"content_type\":\"MARKDOWN\",\"content\":\"TBD\"}"

call :post_expect "[2/6] Protected action blocked" "%ADMIN_URL%/legal/documents" "%CREATE_BODY%" "428" || goto :fail

call :check_get "[3/6] Fetch required docs" "%CORE_ROOT%/legal/required" "%AUTH_HEADER%" "200" || goto :fail

for /f "usebackq tokens=*" %%c in (`python -c "import json; data=json.load(open('legal_required.json')); print(' '.join([f\"{d['code']}|{d['required_version']}|{d['locale']}\" for d in data.get('required',[])]))"`) do set "DOCS=%%c"
if "%DOCS%"=="" (
  echo [WARN] No required docs found. Seed legal docs before running.
  goto :fail
)

for %%d in (%DOCS%) do (
  for /f "tokens=1-3 delims=|" %%a in ("%%d") do (
    call :post_expect "[4/6] Accept %%a" "%CORE_ROOT%/legal/accept" "{\"code\":\"%%a\",\"version\":\"%%b\",\"locale\":\"%%c\",\"accepted\":true}" "200" || goto :fail
  )
)

call :post_expect "[5/6] Protected action allowed" "%ADMIN_URL%/legal/documents" "%CREATE_BODY%" "200" || goto :fail

call :check_get "[6/6] Fetch acceptances" "%ADMIN_URL%/legal/acceptances" "%AUTH_HEADER%" "200" || goto :fail

echo [SMOKE] Legal gate smoke completed.
exit /b 0

:check_get
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -w "%%{http_code}" -H "%HEADER%" -o legal_required.json "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:post_expect
set "LABEL=%~1"
set "URL=%~2"
set "BODY=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%AUTH_HEADER%" -H "Content-Type: application/json" -d "%BODY%" -X POST "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

:fail
echo [SMOKE] Failed.
exit /b 1
