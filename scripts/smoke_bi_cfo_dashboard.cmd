@echo off
setlocal enabledelayedexpansion

set "BASE_URL=http://localhost"
set "CORE_ADMIN=%BASE_URL%/api/core/api/v1/admin"
set "CORE_BI=%BASE_URL%/api/core/bi"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@example.com"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=change-me"

echo [1/4] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :post_step "[2/4] BI sync init" "%CORE_ADMIN%/bi/sync/init" "" "%AUTH_HEADER%" "200" || exit /b 1
call :post_step "[3/4] BI sync incremental" "%CORE_ADMIN%/bi/sync/run" "" "%AUTH_HEADER%" "200" || exit /b 1

echo [4/4] CFO dashboard overview...
curl -s -S -H "%AUTH_HEADER%" "%CORE_BI%/cfo/overview?from=2024-01-01&to=2024-01-31" > cfo_overview.json
python -c "import json; d=json.load(open('cfo_overview.json')); totals=d.get('totals') or {}; required=['gross_revenue','net_revenue','commission_income','vat','refunds','penalties','margin']; missing=[k for k in required if k not in totals]; assert not missing, f'Missing totals: {missing}'; assert all(totals[k] is not None for k in required); print('OK totals', totals)" || exit /b 1

echo [SMOKE] CFO dashboard has data.
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
