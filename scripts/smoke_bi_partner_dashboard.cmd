@echo off
setlocal

if "%CORE_API_BASE%"=="" set "CORE_API_BASE=http://localhost:8001"
if "%CORE_BASE%"=="" set "CORE_BASE=/api/core"
set "CORE_ADMIN=%CORE_API_BASE%%CORE_BASE%/v1/admin"
set "CORE_BI=%CORE_API_BASE%%CORE_BASE%/bi"
set "TMP_DIR=%~dp0_tmp\smoke_bi_partner_dashboard"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%" >nul 2>&1

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"
if "%PARTNER_ID%"=="" set "PARTNER_ID=partner-1"

echo [1/4] Fetch admin token...
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"

call :post_step "[2/4] BI sync init" "%CORE_ADMIN%/bi/sync/init" "%AUTH_HEADER%" "%TMP_DIR%\bi_sync_init.json"
if errorlevel 1 exit /b 1
call :post_step "[3/4] BI sync incremental" "%CORE_ADMIN%/bi/sync/run" "%AUTH_HEADER%" "%TMP_DIR%\bi_sync_run.json"
if errorlevel 1 exit /b 1

echo [4/4] Partner performance dashboard...
call :get_step "[4/4] Partner performance dashboard" "%CORE_BI%/partner/performance?from=2024-01-01&to=2024-01-31&partner_id=%PARTNER_ID%" "%AUTH_HEADER%" "%TMP_DIR%\partner_perf.json"
if errorlevel 1 exit /b 1
python -c "import json; d=json.load(open(r'%TMP_DIR%\\partner_perf.json')); items=d.get('items') or []; assert isinstance(items, list); print('OK items', len(items))" || exit /b 1

echo [SMOKE] Partner dashboard has data.
exit /b 0

:post_step
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "OUT=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -H "%HEADER%" -X POST "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="200" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected 200 got %CODE%
type "%OUT%"
exit /b 1

:get_step
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "OUT=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -S -o "%OUT%" -w "%%{http_code}" -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="200" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected 200 got %CODE%
type "%OUT%"
exit /b 1
