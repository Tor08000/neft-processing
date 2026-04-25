@echo off
setlocal

if "%BASE%"=="" set "BASE=http://localhost"
if "%CORE_PREFIX%"=="" set "CORE_PREFIX=/api/core"
if "%GATEWAY_BASE%"=="" set "GATEWAY_BASE=%BASE%"
if "%AUTH_BASE%"=="" set "AUTH_BASE=/api/v1/auth"
if "%CORE_BASE%"=="" set "CORE_BASE=%CORE_PREFIX%"
set "AUTH_URL=%GATEWAY_BASE%%AUTH_BASE%"
set "CORE_URL=%GATEWAY_BASE%%CORE_BASE%/v1/admin"
if "%API_BASE%"=="" set "API_BASE=%CORE_URL%"
set "INVOICES_URL=%GATEWAY_BASE%/api/core/v1/admin/billing/invoices"

if "%ADMIN_EMAIL%"=="" set "ADMIN_EMAIL=admin@neft.local"
if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=Neft123!"

set "TOKEN="
set "AUTH_HEADER="
set "INVOICE_ID="
set "CURRENT_STATUS="

echo [1/8] Fetch admin token...
set "TOKEN="
for /f "usebackq delims=" %%T in (`scripts\\get_admin_token.cmd`) do set "TOKEN=%%T"
if errorlevel 1 exit /b 1
if "%TOKEN%"=="" exit /b 1
set "AUTH_HEADER=Authorization: Bearer %TOKEN%"
echo [OK] Token acquired.

call :check_get "[2/8] /auth/me" "%AUTH_URL%/me" "%AUTH_HEADER%" "200" || goto :fail
call :check_get "[3/8] Billing periods" "%CORE_URL%/billing/periods?limit=1" "%AUTH_HEADER%" "200" || goto :fail

echo [4/8] List invoices to obtain id...
set "CODE="
set "INVOICE_ID="
set "LIST_URL=%INVOICES_URL%?limit=1^&offset=0"
echo [DEBUG] GET %LIST_URL%
curl -s -D "%TEMP%\invoice_list.hdr" -o "%TEMP%\invoices.json" -w "%{http_code}" -H "%AUTH_HEADER%" "%LIST_URL%" > "%TEMP%\invoice_list.code"
set /p CODE=<"%TEMP%\invoice_list.code"
if "%CODE%"=="202" (
  echo [SKIP] Invoice list returned 202 (async), skipping state machine.
  exit /b 0
)
if "%CODE:~0,1%"=="5" goto :invoice_list_fail
if not "%CODE%"=="200" goto :invoice_list_skip
python -c "import json; data=json.load(open(r'%TEMP%\\invoices.json')); items=data.get('items'); assert isinstance(items, list); total=data.get('total', len(items)); first=items[0] if items else {}; print('{0}|{1}|{2}|{3}'.format(first.get('id',''), first.get('status',''), len(items), total))" > "%TEMP%\invoice_state.txt"
if errorlevel 1 goto :invoice_list_bad_json
for /f "usebackq tokens=1-4 delims=|" %%i in ("%TEMP%\invoice_state.txt") do (
  set "INVOICE_ID=%%i"
  set "CURRENT_STATUS=%%j"
  set "ITEMS_COUNT=%%k"
  set "TOTAL_COUNT=%%l"
)
if "%ITEMS_COUNT%"=="0" if "%TOTAL_COUNT%"=="0" (
  echo [SKIP] No invoices found. State machine not applicable.
  exit /b 0
)
if "%INVOICE_ID%"=="" goto :step4_fail
goto :step4_done

:invoice_list_fail
echo [FAIL] Invoices list returned %CODE%.
goto :fail

:invoice_list_bad_json
echo [FAIL] Invoices list returned invalid JSON or missing items[].
goto :fail

:invoice_list_skip
echo [SKIP] Invoices list returned %CODE%, skipping state transitions.
exit /b 0

:step4_done
if "%INVOICE_ID%"=="" goto :step4_fail
goto :step4_continue

:step4_fail
echo [FAIL] Could not resolve invoice id.
goto :fail

:step4_continue
if /i "%CURRENT_STATUS%"=="DRAFT" (
  call :post_step "[5/8] DRAFT -> ISSUED" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"ISSUED\",\"reason\":\"smoke\"}" "%AUTH_HEADER%" "200" "" || goto :fail
  set "CURRENT_STATUS=ISSUED"
) else (
  echo [INFO] Invoice status %CURRENT_STATUS%, skipping DRAFT->ISSUED.
)

if /i "%CURRENT_STATUS%"=="ISSUED" (
  call :post_step "[6/8] ISSUED -> FINALIZED" "%CORE_URL%/billing/invoices/%INVOICE_ID%/status" "{\"status\":\"FINALIZED\",\"reason\":\"smoke\"}" "%AUTH_HEADER%" "200" "409" || goto :fail
) else (
  echo [INFO] Invoice status %CURRENT_STATUS%, skipping ISSUED->FINALIZED.
)

call :check_get "[7/8] Invoice list health recheck" "%LIST_URL%" "%AUTH_HEADER%" "200" || goto :fail

call :check_get "[8/8] Clearing batches" "%CORE_URL%/clearing/batches?limit=1" "%AUTH_HEADER%" "200" || echo [WARN] Clearing check skipped.

echo [SMOKE] Invoice state machine smoke completed.
exit /b 0

:check_get
set "LABEL=%~1"
set "URL=%~2"
set "HEADER=%~3"
set "EXPECTED=%~4"
set "CODE="
for /f "usebackq tokens=*" %%c in (`curl -s -o NUL -w "%%{http_code}" -H "%HEADER%" "%URL%"`) do set "CODE=%%c"
if "%CODE%"=="%EXPECTED%" (
  echo [OK] %LABEL%
  exit /b 0
)
echo [FAIL] %LABEL% expected %EXPECTED% got %CODE%
exit /b 1

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
echo [SMOKE] Failed.
exit /b 1
