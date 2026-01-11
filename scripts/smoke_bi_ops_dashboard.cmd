@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"
set "AUTH_URL=%BASE_URL%/api/auth/api/v1/auth"
set "CORE_ADMIN=%BASE_URL%/api/core/api/v1/admin"
set "CORE_BI=%BASE_URL%/api/core/bi"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

echo [1/4] Login to auth-host...
curl -s -S -X POST "%AUTH_URL%/login" -H "Content-Type: application/json" -d "{\"email\":\"%ADMIN_EMAIL%\",\"password\":\"%ADMIN_PASSWORD%\"}" > login.json
for /f "usebackq tokens=*" %%t in (`python -c "import json; print(json.load(open('login.json')).get('access_token',''))"`) do set "TOKEN=%%t"
if "%TOKEN%"=="" (
  echo [FAIL] No access_token returned.
  exit /b 1
)
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :post_step "[2/4] BI sync init" "%CORE_ADMIN%/bi/sync/init" "" "%AUTH_HEADER%" "200" || exit /b 1
call :post_step "[3/4] BI sync incremental" "%CORE_ADMIN%/bi/sync/run" "" "%AUTH_HEADER%" "200" || exit /b 1

echo [4/4] Ops SLA dashboard...
curl -s -S -H "%AUTH_HEADER%" "%CORE_BI%/ops/sla?from=2024-01-01&to=2024-01-31" > ops_sla.json
python -c "import json; d=json.load(open('ops_sla.json')); totals=d.get('totals') or {}; required=['total_orders','sla_breaches']; missing=[k for k in required if k not in totals]; assert not missing, f'Missing totals: {missing}'; assert all(totals[k] is not None for k in required); print('OK totals', totals)" || exit /b 1

echo [SMOKE] Ops dashboard has data.
exit /b 0

:post_step
set "LABEL=%~1"
set "URL=%~2"
set "BODY=%~3"
set "HEADER=%~4"
set "EXPECTED=%~5"
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
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1
